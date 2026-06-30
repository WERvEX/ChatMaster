"""Seed local workspace data from settings and identity YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from chatmaster.db.models import Identity, User, Workspace
from chatmaster.identities.loader import YAML_PATH
from chatmaster.identities.schema import IdentityConfig


class SeedSettings(Protocol):
    local_workspace_id: str
    local_user_id: str


def _load_identity_configs(path: Path) -> list[IdentityConfig]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    items = raw.get("identities") if isinstance(raw, dict) else None
    if not items:
        return []
    return [IdentityConfig(**item) for item in items]


def seed_local_data(
    db: Session,
    settings: SeedSettings,
    identities_path: Path = YAML_PATH,
) -> None:
    workspace = db.get(Workspace, settings.local_workspace_id)
    if workspace is None:
        workspace = Workspace(id=settings.local_workspace_id, name="Local Workspace")
        db.add(workspace)

    user = db.get(User, settings.local_user_id)
    if user is None:
        user = User(
            id=settings.local_user_id,
            workspace_id=settings.local_workspace_id,
            email=None,
            display_name="Local User",
        )
        db.add(user)

    for cfg in _load_identity_configs(identities_path):
        stmt = select(Identity).where(
            Identity.workspace_id == settings.local_workspace_id,
            Identity.slug == cfg.id,
        )
        identity = db.execute(stmt).scalar_one_or_none()
        if identity is None:
            identity = Identity(
                id=cfg.id,
                workspace_id=settings.local_workspace_id,
                slug=cfg.id,
                name=cfg.name,
                description=cfg.description,
                system_prompt=cfg.system_prompt,
                private_collection=cfg.private_collection,
                generation_model=cfg.generation_model,
                embedding_model=cfg.embedding_model,
                retrieval_config_json=cfg.retrieval.model_dump(),
                is_active=True,
            )
            db.add(identity)
        else:
            identity.name = cfg.name
            identity.description = cfg.description
            identity.system_prompt = cfg.system_prompt
            identity.private_collection = cfg.private_collection
            identity.generation_model = cfg.generation_model
            identity.embedding_model = cfg.embedding_model
            identity.retrieval_config_json = cfg.retrieval.model_dump()
            identity.is_active = True

    db.commit()
