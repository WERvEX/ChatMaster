"""Database-backed provider configuration service."""

from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from chatmaster.ai.providers import (
    ChatProviderConfig,
    EmbeddingProviderConfig,
    ProvidersConfig,
    is_masked,
)
from chatmaster.db.models import ProviderConfig


class ProviderSettings(Protocol):
    default_llm_provider: str
    openai_base_url: str | None
    openai_api_key: str | None
    default_generation_model: str
    default_embedding_provider: str
    default_embedding_model: str
    huggingface_endpoint: str | None


def seed_from_settings(settings: ProviderSettings) -> ProvidersConfig:
    return ProvidersConfig(
        chat=ChatProviderConfig(
            provider=settings.default_llm_provider,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.default_generation_model,
        ),
        embedding=EmbeddingProviderConfig(
            provider=settings.default_embedding_provider,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.default_embedding_model,
            huggingface_endpoint=settings.huggingface_endpoint,
        ),
    )


def _row_to_config(row: ProviderConfig) -> ProvidersConfig:
    return ProvidersConfig(
        chat=ChatProviderConfig(
            provider=row.chat_provider,
            base_url=row.chat_base_url,
            api_key=row.chat_api_key_encrypted,
            model=row.chat_model,
        ),
        embedding=EmbeddingProviderConfig(
            provider=row.embedding_provider,
            base_url=row.embedding_base_url,
            api_key=row.embedding_api_key_encrypted,
            model=row.embedding_model,
            huggingface_endpoint=row.huggingface_endpoint,
        ),
    )


def _find_row(db: Session, workspace_id: str) -> ProviderConfig | None:
    stmt = select(ProviderConfig).where(ProviderConfig.workspace_id == workspace_id)
    return db.execute(stmt).scalar_one_or_none()


def get_provider_config(
    db: Session,
    workspace_id: str,
    settings: ProviderSettings,
) -> ProvidersConfig:
    row = _find_row(db, workspace_id)
    if row is None:
        return seed_from_settings(settings)
    return _row_to_config(row)


def save_provider_config(
    db: Session,
    workspace_id: str,
    payload: ProvidersConfig,
    settings: ProviderSettings,
) -> ProvidersConfig:
    current = get_provider_config(db, workspace_id, settings)
    row = _find_row(db, workspace_id)
    if row is None:
        row = ProviderConfig(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            chat_provider=payload.chat.provider,
            chat_base_url=payload.chat.base_url,
            chat_api_key_encrypted=None,
            chat_model=payload.chat.model,
            embedding_provider=payload.embedding.provider,
            embedding_base_url=payload.embedding.base_url,
            embedding_api_key_encrypted=None,
            embedding_model=payload.embedding.model,
            huggingface_endpoint=payload.embedding.huggingface_endpoint,
        )
        db.add(row)

    row.chat_provider = payload.chat.provider
    row.chat_base_url = payload.chat.base_url
    row.chat_api_key_encrypted = (
        current.chat.api_key if is_masked(payload.chat.api_key) else payload.chat.api_key
    )
    row.chat_model = payload.chat.model
    row.embedding_provider = payload.embedding.provider
    row.embedding_base_url = payload.embedding.base_url
    row.embedding_api_key_encrypted = (
        current.embedding.api_key
        if is_masked(payload.embedding.api_key)
        else payload.embedding.api_key
    )
    row.embedding_model = payload.embedding.model
    row.huggingface_endpoint = payload.embedding.huggingface_endpoint

    db.commit()
    db.refresh(row)
    return _row_to_config(row)
