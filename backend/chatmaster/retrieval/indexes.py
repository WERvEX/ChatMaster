"""Non-destructive Qdrant index version rebuilds."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from chatmaster.ai.models import build_embeddings
from chatmaster.ai.vectorstore import delete_collection, ensure_collection
from chatmaster.config import get_settings
from chatmaster.db.models import Document, IndexVersion
from chatmaster.identities.service import get_identity_model, to_config


def embedding_fingerprint() -> str:
    from chatmaster.ai.providers import get_provider_config

    cfg = get_provider_config().embedding
    payload = {
        "provider": cfg.provider.lower(),
        "base_url": cfg.base_url or "",
        "model": cfg.model,
        "huggingface_endpoint": cfg.huggingface_endpoint or "",
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def ensure_active_version(
    db: Session,
    *,
    workspace_id: str,
    logical_name: str,
    identity_id: str | None,
    embeddings,
) -> IndexVersion:
    namespace = "common" if identity_id is None else "private"
    version = db.scalars(
        select(IndexVersion)
        .where(
            IndexVersion.workspace_id == workspace_id,
            IndexVersion.namespace == namespace,
            IndexVersion.identity_id == identity_id,
            IndexVersion.status.in_(("active", "stale")),
        )
        .order_by(IndexVersion.updated_at.desc())
    ).first()
    if version is not None:
        return version
    version = IndexVersion(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        namespace=namespace,
        identity_id=identity_id,
        logical_name=logical_name,
        collection_name=logical_name,
        embedding_provider=type(embeddings).__name__,
        embedding_model=str(
            getattr(embeddings, "model_name", getattr(embeddings, "model", "default"))
        ),
        embedding_dim=len(embeddings.embed_query("dimension probe")),
        config_fingerprint=embedding_fingerprint(),
        status="active",
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


class IndexRebuildRequired(RuntimeError):
    """The configured embedding model no longer matches an active index."""


def assert_indexes_fresh(db: Session, *, workspace_id: str) -> None:
    stale = db.scalars(
        select(IndexVersion).where(
            IndexVersion.workspace_id == workspace_id,
            IndexVersion.status == "stale",
        )
    ).first()
    if stale is not None:
        raise IndexRebuildRequired("Embedding 配置已变化，请先重建知识库索引。")


def active_collection(
    db: Session,
    *,
    workspace_id: str,
    logical_name: str,
    identity_id: str | None,
) -> str:
    """Resolve the active physical collection, with legacy-name fallback."""
    namespace = "common" if identity_id is None else "private"
    return (
        db.scalars(
            select(IndexVersion.collection_name)
            .where(
                IndexVersion.workspace_id == workspace_id,
                IndexVersion.namespace == namespace,
                IndexVersion.identity_id == identity_id,
                IndexVersion.status == "active",
            )
            .order_by(IndexVersion.updated_at.desc())
        ).first()
        or logical_name
    )


def rebuild_index(
    db: Session,
    *,
    workspace_id: str,
    identity_id: str | None,
    target: str,
) -> IndexVersion:
    """Build a new physical collection and activate it only after success."""
    if target not in {"private", "common"}:
        raise ValueError("target must be 'private' or 'common'")
    if target == "private" and not identity_id:
        raise ValueError("identity_id is required for a private index rebuild")
    identity = (
        to_config(
            get_identity_model(
                db,
                workspace_id=workspace_id,
                identity_id=identity_id,
            )
        )
        if identity_id
        else None
    )
    settings = get_settings()
    namespace = "common" if target == "common" else "private"
    version_identity_id = None if namespace == "common" else identity_id
    logical_name = settings.common_collection if target == "common" else identity.private_collection
    physical_name = f"{logical_name}__v_{uuid.uuid4().hex[:12]}"
    embeddings = build_embeddings(None if target == "common" else identity)
    dim = len(embeddings.embed_query("dimension probe"))
    ensure_collection(physical_name, dim)
    version = IndexVersion(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        namespace=namespace,
        identity_id=version_identity_id,
        collection_name=physical_name,
        logical_name=logical_name,
        embedding_provider=type(embeddings).__name__,
        embedding_model=str(getattr(embeddings, "model_name", "default")),
        embedding_dim=dim,
        config_fingerprint=embedding_fingerprint(),
        status="building",
    )
    db.add(version)
    db.commit()
    try:
        # Delayed import avoids a module-load cycle with retrieval.
        from chatmaster.services.ingest_service import ingest

        stmt = select(Document).where(
            Document.workspace_id == workspace_id,
            Document.namespace == namespace,
            Document.status == "indexed",
        )
        if version_identity_id is not None:
            stmt = stmt.where(Document.identity_id == version_identity_id)
        for document in db.scalars(stmt):
            result = ingest(
                identity_id,
                [Path(document.storage_path)],
                target,
                physical_name,
                workspace_id=workspace_id,
                db=db,
            )
            errors = [item.error for item in result.files if item.error]
            if errors:
                raise RuntimeError("; ".join(errors))
    except Exception:
        version.status = "failed"
        db.commit()
        raise
    for old in db.scalars(
        select(IndexVersion).where(
            IndexVersion.workspace_id == workspace_id,
            IndexVersion.namespace == namespace,
            IndexVersion.identity_id == version_identity_id,
            IndexVersion.status.in_(("active", "stale")),
        )
    ):
        old.status = "retired"
    version.status = "active"
    db.commit()
    return version


def cleanup_retired_indexes(db: Session, *, workspace_id: str, confirm: bool = False) -> list[str]:
    """List, or with confirmation delete, failed and retired physical collections."""
    versions = list(
        db.scalars(
            select(IndexVersion).where(
                IndexVersion.workspace_id == workspace_id,
                IndexVersion.status.in_(("failed", "retired")),
            )
        )
    )
    names = [version.collection_name for version in versions]
    if confirm:
        for version in versions:
            delete_collection(version.collection_name)
            version.status = "deleted"
        db.commit()
    return names
