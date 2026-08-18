"""Runtime-customizable provider configuration.

Users edit the chat + embedding provider settings (base_url, api_key, model)
from the web UI "API 配置" page. The config persists to a JSON file
(``Settings.providers_file``); the ``.env`` / :class:`Settings` values act as
the seed defaults on first run. This replaces the old hardcoded
``if provider == "openai"/"anthropic"/"huggingface"`` branches in
``models.py`` — that module now reads from :func:`get_provider_config` here.
"""

from __future__ import annotations

import threading
import uuid
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from chatmaster.config import get_settings

_LOCK = threading.Lock()

# Mask sentinel embedded in masked keys (see :func:`mask_key`).
_MASK_TOKEN = "****"


class ChatProviderConfig(BaseModel):
    """The active chat (generation) provider. OpenAI-compatible or Anthropic."""

    provider: Literal["openai", "anthropic", "deepseek", "moonshot", "openai-compatible"] = "openai"
    base_url: str | None = (
        None  # None => library default (OpenAI). DeepSeek: https://api.deepseek.com/v1
    )
    api_key: str | None = None
    model: str = Field(default="deepseek-v4-pro", min_length=1, max_length=255)
    clear_api_key: bool = False


class EmbeddingProviderConfig(BaseModel):
    """The active embedding provider. Local HuggingFace (default) or OpenAI-compatible."""

    provider: Literal["huggingface", "openai", "openai-compatible"] = "huggingface"
    base_url: str | None = None  # only used for openai-compatible embeddings
    api_key: str | None = None
    model: str = Field(default="BAAI/bge-small-zh-v1.5", min_length=1, max_length=255)
    huggingface_endpoint: str | None = "https://hf-mirror.com"  # HF download mirror
    clear_api_key: bool = False


class ProvidersConfig(BaseModel):
    chat: ChatProviderConfig
    embedding: EmbeddingProviderConfig


def seed_from_settings() -> ProvidersConfig:
    """Build the initial provider config from .env/Settings (used on first run)."""
    s = get_settings()
    return ProvidersConfig(
        chat=ChatProviderConfig(
            provider=s.default_llm_provider,
            base_url=s.openai_base_url,
            api_key=s.openai_api_key,
            model=s.default_generation_model,
        ),
        embedding=EmbeddingProviderConfig(
            provider=s.default_embedding_provider,
            base_url=s.openai_base_url,
            api_key=s.openai_api_key,
            model=s.default_embedding_model,
            huggingface_endpoint=s.huggingface_endpoint,
        ),
    )


@lru_cache(maxsize=1)
def get_provider_config(workspace_id: str | None = None) -> ProvidersConfig:
    """Return the active provider config.

    Loads from the local database when available; falls back to environment
    seed values only when the database is not initialized. The
    result is cached — call
    :func:`save_provider_config` (which clears the cache) after edits.
    """
    try:
        from chatmaster.db.session import SessionLocal
        from chatmaster.providers.service import get_provider_config as _get_db_config

        settings = get_settings()
        with SessionLocal() as db:
            return _get_db_config(db, workspace_id or settings.local_workspace_id, settings)
    except SQLAlchemyError:
        pass

    return seed_from_settings()


def save_provider_config(cfg: ProvidersConfig, workspace_id: str | None = None) -> ProvidersConfig:
    """Persist encrypted ``cfg`` and invalidate all downstream caches."""
    try:
        from chatmaster.db.session import SessionLocal
        from chatmaster.providers.service import get_provider_config as _get_db_config
        from chatmaster.providers.service import save_provider_config as _save_db_config

        settings = get_settings()
        with _LOCK, SessionLocal() as db:
            before = _get_db_config(db, workspace_id or settings.local_workspace_id, settings)
            _save_db_config(db, workspace_id or settings.local_workspace_id, cfg, settings)
            before_embedding = (
                before.embedding.provider,
                before.embedding.base_url,
                before.embedding.model,
                before.embedding.huggingface_endpoint,
            )
            after_embedding = (
                cfg.embedding.provider,
                cfg.embedding.base_url,
                cfg.embedding.model,
                cfg.embedding.huggingface_endpoint,
            )
            if before_embedding != after_embedding:
                from sqlalchemy import update

                from chatmaster.db.models import IndexVersion
                from chatmaster.identities.service import list_identity_models

                db.execute(
                    update(IndexVersion)
                    .where(
                        IndexVersion.workspace_id == (workspace_id or settings.local_workspace_id),
                        IndexVersion.status == "active",
                    )
                    .values(status="stale")
                )
                existing_scopes = {
                    (item.namespace, item.identity_id)
                    for item in db.scalars(
                        select(IndexVersion).where(
                            IndexVersion.workspace_id
                            == (workspace_id or settings.local_workspace_id)
                        )
                    )
                }
                scopes = [
                    ("common", None, settings.common_collection),
                    *[
                        ("private", identity.id, identity.private_collection)
                        for identity in list_identity_models(
                            db,
                            workspace_id=workspace_id or settings.local_workspace_id,
                            include_archived=True,
                        )
                    ],
                ]
                for namespace, identity_id, logical_name in scopes:
                    if (namespace, identity_id) in existing_scopes:
                        continue
                    db.add(
                        IndexVersion(
                            id=str(uuid.uuid4()),
                            workspace_id=workspace_id or settings.local_workspace_id,
                            namespace=namespace,
                            identity_id=identity_id,
                            logical_name=logical_name,
                            collection_name=logical_name,
                            embedding_provider=before.embedding.provider,
                            embedding_model=before.embedding.model,
                            embedding_dim=0,
                            config_fingerprint="legacy",
                            status="stale",
                        )
                    )
                db.commit()
    except SQLAlchemyError as exc:
        # The historical JSON fallback stores API keys in plaintext. Refuse to
        # persist credentials there when the relational store is unavailable.
        raise RuntimeError(
            "Provider configuration database is unavailable; configuration was not saved."
        ) from exc
    get_provider_config.cache_clear()

    # The model/embedding builders cache instances by (model, base_url, key);
    # new credentials/model must take effect immediately.
    from chatmaster.ai import models as _models

    _models.clear_caches()
    return get_provider_config(workspace_id)


def mask_key(key: str | None) -> str | None:
    """Return a masked copy of an API key for safe display in the UI."""
    if not key:
        return None
    if len(key) <= 8:
        return _MASK_TOKEN
    return key[:3] + _MASK_TOKEN + key[-4:]


def is_masked(key: str | None) -> bool:
    """True when ``key`` is empty or a masked value returned by :func:`mask_key`.

    Used on save to decide whether to keep the previously stored key rather than
    overwriting it with the display mask.
    """
    return (not key) or (_MASK_TOKEN in key)
