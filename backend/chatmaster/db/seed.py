"""Seed local workspace data from settings and identity YAML once."""

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
                is_system=False,
            )
            db.add(identity)

    fallback = db.get(Identity, "general_assistant")
    if fallback is None:
        db.add(
            Identity(
                id="general_assistant",
                workspace_id=settings.local_workspace_id,
                slug="general_assistant",
                name="通用助手",
                description="随时待命的通用 AI 助手。",
                system_prompt=(
                    "你是一位可靠、清晰、友善的通用 AI 助手。"
                    "优先准确回答问题；信息不足时明确说明，并给出可执行的下一步。"
                ),
                avatar_url="/default-assistant.png",
                private_collection="chatmaster_general_assistant",
                generation_model=None,
                embedding_model=None,
                retrieval_config_json={
                    "top_k": 6,
                    "private_weight": 0.0,
                    "common_weight": 1.0,
                    "min_chunks_common": 2,
                },
                is_active=True,
                is_system=True,
            )
        )

    db.commit()
