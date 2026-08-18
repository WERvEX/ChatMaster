"""Ingestion: load -> chunk -> embed -> upsert. Shared by the CLI and web upload."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from chatmaster.ai.chunkers import split_documents
from chatmaster.ai.loaders import UnsupportedFileType, load_file
from chatmaster.ai.models import build_embeddings
from chatmaster.ai.vectorstore import delete_points, get_store
from chatmaster.config import get_settings
from chatmaster.db.models import Document, DocumentChunk, IndexVersion
from chatmaster.identities.service import get_identity_model, to_config
from chatmaster.schemas.api import IngestFileResult, IngestResult

logger = logging.getLogger(__name__)


class IngestFailed(RuntimeError):
    """Raised when one or more files could not be indexed."""


def ingest(
    identity_id: str | None,
    files: list[Path],
    target: str = "private",
    collection_name: str | None = None,
    *,
    workspace_id: str | None = None,
    db: Session | None = None,
) -> IngestResult:
    """Ingest files into the identity's private collection or the common one.

    `target` is "private" (identity.private_collection) or "common" (COMMON_COLLECTION).
    """
    if target not in {"private", "common"}:
        raise ValueError("target must be 'private' or 'common'")

    settings = get_settings()
    if target == "private" and not identity_id:
        raise ValueError("identity_id is required for private ingestion")
    if identity_id and (db is None or workspace_id is None):
        raise ValueError("workspace_id and db are required for identity ingestion")
    identity = (
        to_config(
            get_identity_model(
                db,
                workspace_id=workspace_id,
                identity_id=identity_id,
            )
        )
        if identity_id and db is not None and workspace_id is not None
        else None
    )

    logical_collection = (
        settings.common_collection if target == "common" else identity.private_collection
    )
    if collection_name is None:
        if db is None or workspace_id is None:
            raise ValueError(
                "workspace_id and db are required when resolving the active collection"
            )
        from chatmaster.retrieval.indexes import active_collection, assert_indexes_fresh

        assert_indexes_fresh(
            db,
            workspace_id=workspace_id,
            identity_id=identity_id,
            include_private=target == "private",
        )
        collection = active_collection(
            db,
            workspace_id=workspace_id,
            logical_name=logical_collection,
            identity_id=None if target == "common" else identity_id,
        )
    else:
        collection = collection_name
    embeddings = build_embeddings(None if target == "common" else identity)
    version = None
    if db is not None and workspace_id is not None:
        from chatmaster.retrieval.indexes import ensure_active_version

        if collection_name is not None:
            version = db.scalars(
                select(IndexVersion).where(
                    IndexVersion.workspace_id == workspace_id,
                    IndexVersion.collection_name == collection_name,
                )
            ).first()
        if version is None:
            version = ensure_active_version(
                db,
                workspace_id=workspace_id,
                logical_name=logical_collection,
                identity_id=None if target == "common" else identity_id,
                embeddings=embeddings,
            )
    store = get_store(collection, embeddings)

    file_results: list[IngestFileResult] = []
    total_chunks = 0

    for path in files:
        written_point_ids: list[str] = []
        try:
            docs = load_file(path, identity_id=identity_id or "common")
            chunks = split_documents(docs)
            if chunks:
                document = (
                    db.query(Document).filter(Document.storage_path == str(path)).one_or_none()
                    if db is not None
                    else None
                )
                if document is not None and version is not None and workspace_id is not None:
                    db.execute(
                        delete(DocumentChunk).where(
                            DocumentChunk.document_id == document.id,
                            DocumentChunk.index_version_id == version.id,
                        )
                    )
                    point_ids: list[str] = []
                    for index, chunk in enumerate(chunks):
                        point_id = str(
                            uuid.uuid5(
                                uuid.NAMESPACE_URL,
                                f"chatmaster:{version.id}:{document.id}:{index}",
                            )
                        )
                        chunk.metadata.update(
                            {
                                "workspace_id": workspace_id,
                                "document_id": document.id,
                                "chunk_id": point_id,
                                "index_version_id": version.id,
                                "chunk_index": index,
                            }
                        )
                        point_ids.append(point_id)
                        db.add(
                            DocumentChunk(
                                id=point_id,
                                workspace_id=workspace_id,
                                document_id=document.id,
                                index_version_id=version.id,
                                qdrant_point_id=point_id,
                                chunk_index=index,
                                text=chunk.page_content,
                                metadata_json=dict(chunk.metadata),
                            )
                        )
                    written_point_ids = point_ids
                    try:
                        store.add_documents(chunks, ids=point_ids)
                        db.commit()
                    except Exception:
                        db.rollback()
                        if written_point_ids:
                            try:
                                delete_points(collection, written_point_ids)
                            except Exception as cleanup_exc:  # noqa: BLE001
                                logger.warning(
                                    "Failed to compensate Qdrant points collection=%s count=%d: %s",
                                    collection,
                                    len(written_point_ids),
                                    cleanup_exc,
                                )
                        raise
                else:
                    store.add_documents(chunks)
            file_results.append(IngestFileResult(file=path.name, chunks=len(chunks)))
            total_chunks += len(chunks)
        except UnsupportedFileType as e:
            if db is not None:
                db.rollback()
            file_results.append(IngestFileResult(file=path.name, error=str(e)))
        except Exception as e:  # noqa: BLE001
            if db is not None:
                db.rollback()
            file_results.append(IngestFileResult(file=path.name, error=f"{type(e).__name__}: {e}"))

    return IngestResult(
        identity_id=identity_id,
        target=target,
        collection=collection,
        files=file_results,
        total_chunks=total_chunks,
    )
