"""Database-backed identity/persona management."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from chatmaster.config import get_settings
from chatmaster.db.models import Identity
from chatmaster.identities.schema import (
    IdentityConfig,
    IdentityCreate,
    IdentityDetail,
    IdentityOut,
    IdentityUpdate,
    RetrievalConfig,
)


class IdentityNotFound(KeyError):
    """Raised when an identity is missing, archived, or outside the workspace."""


def _query(db: Session, workspace_id: str):
    return select(Identity).where(Identity.workspace_id == workspace_id)


def get_identity_model(
    db: Session,
    *,
    workspace_id: str,
    identity_id: str,
    include_archived: bool = False,
) -> Identity:
    identity = db.get(Identity, identity_id)
    if (
        identity is None
        or identity.workspace_id != workspace_id
        or (not include_archived and not identity.is_active)
    ):
        raise IdentityNotFound(identity_id)
    return identity


def list_identity_models(
    db: Session,
    *,
    workspace_id: str,
    include_archived: bool = False,
) -> list[Identity]:
    stmt = _query(db, workspace_id)
    if not include_archived:
        stmt = stmt.where(Identity.is_active.is_(True))
    return list(db.scalars(stmt.order_by(Identity.is_system.desc(), Identity.created_at.asc())))


def to_config(identity: Identity) -> IdentityConfig:
    return IdentityConfig(
        id=identity.id,
        name=identity.name,
        description=identity.description,
        system_prompt=identity.system_prompt,
        private_collection=identity.private_collection,
        embedding_model=identity.embedding_model,
        generation_model=identity.generation_model,
        uses_private_knowledge=not identity.is_system,
        retrieval=RetrievalConfig(**(identity.retrieval_config_json or {})),
    )


def get_identity_config(identity_id: str, workspace_id: str | None = None) -> IdentityConfig:
    from chatmaster.db.session import SessionLocal

    target_workspace = workspace_id or get_settings().local_workspace_id
    with SessionLocal() as db:
        return to_config(
            get_identity_model(
                db,
                workspace_id=target_workspace,
                identity_id=identity_id,
            )
        )


def to_out(identity: Identity) -> IdentityOut:
    return IdentityOut(
        id=identity.id,
        name=identity.name,
        description=identity.description,
        avatar_url=identity.avatar_url,
        generation_model=identity.generation_model,
        retrieval=RetrievalConfig(**(identity.retrieval_config_json or {})),
        is_archived=not identity.is_active,
        is_system=identity.is_system,
    )


def to_detail(identity: Identity) -> IdentityDetail:
    return IdentityDetail(
        **to_out(identity).model_dump(),
        system_prompt=identity.system_prompt,
        embedding_model=identity.embedding_model,
    )


def create_identity(
    db: Session,
    *,
    workspace_id: str,
    payload: IdentityCreate,
) -> Identity:
    token = uuid.uuid4().hex
    identity = Identity(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        slug=f"persona-{token[:12]}",
        name=payload.name.strip(),
        description=payload.description.strip(),
        system_prompt=payload.system_prompt.strip(),
        avatar_url=payload.avatar_url,
        private_collection=f"chatmaster_persona_{token}",
        generation_model=payload.generation_model or None,
        embedding_model=payload.embedding_model or None,
        retrieval_config_json=payload.retrieval.model_dump(),
        is_active=True,
        is_system=False,
    )
    db.add(identity)
    db.commit()
    db.refresh(identity)
    return identity


def update_identity(
    db: Session,
    *,
    workspace_id: str,
    identity_id: str,
    payload: IdentityUpdate,
) -> Identity:
    identity = get_identity_model(
        db,
        workspace_id=workspace_id,
        identity_id=identity_id,
        include_archived=True,
    )
    if identity.is_system:
        raise PermissionError("System identity cannot be edited")
    identity.name = payload.name.strip()
    identity.description = payload.description.strip()
    identity.system_prompt = payload.system_prompt.strip()
    identity.avatar_url = payload.avatar_url
    identity.generation_model = payload.generation_model or None
    identity.embedding_model = payload.embedding_model or None
    identity.retrieval_config_json = payload.retrieval.model_dump()
    db.commit()
    db.refresh(identity)
    from chatmaster.ai import models as ai_models

    ai_models.clear_caches()
    return identity


def set_archived(
    db: Session,
    *,
    workspace_id: str,
    identity_id: str,
    archived: bool,
) -> Identity:
    identity = get_identity_model(
        db,
        workspace_id=workspace_id,
        identity_id=identity_id,
        include_archived=True,
    )
    if identity.is_system:
        raise PermissionError("System identity cannot be archived")
    identity.is_active = not archived
    db.commit()
    db.refresh(identity)
    return identity


def duplicate_identity(
    db: Session,
    *,
    workspace_id: str,
    identity_id: str,
) -> Identity:
    source = get_identity_model(
        db,
        workspace_id=workspace_id,
        identity_id=identity_id,
        include_archived=True,
    )
    return create_identity(
        db,
        workspace_id=workspace_id,
        payload=IdentityCreate(
            name=f"{source.name} 副本",
            description=source.description,
            system_prompt=source.system_prompt,
            avatar_url=source.avatar_url,
            generation_model=source.generation_model,
            embedding_model=source.embedding_model,
            retrieval=RetrievalConfig(**(source.retrieval_config_json or {})),
        ),
    )
