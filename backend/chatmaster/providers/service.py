"""Database-backed provider configuration service."""

from __future__ import annotations

import uuid
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from chatmaster.ai.providers import (
    ChatProviderConfig,
    EmbeddingProviderConfig,
    ProvidersConfig,
    is_masked,
)
from chatmaster.db.models import ProviderConfig
from chatmaster.providers.security import validate_provider_url


class ProviderSettings(Protocol):
    default_llm_provider: str
    openai_base_url: str | None
    openai_api_key: str | None
    default_generation_model: str
    default_embedding_provider: str
    default_embedding_model: str
    huggingface_endpoint: str | None
    provider_encryption_key: str | None
    allow_private_provider_urls: bool


class ProviderEncryptionError(RuntimeError):
    """Raised when encrypted provider credentials cannot be safely accessed."""


_ENCRYPTED_PREFIX = "fernet:"


def _fernet(settings: ProviderSettings) -> Fernet:
    key = settings.provider_encryption_key
    if not key:
        raise ProviderEncryptionError(
            "PROVIDER_ENCRYPTION_KEY must be configured before storing API keys."
        )
    try:
        return Fernet(key.encode())
    except (TypeError, ValueError) as exc:
        raise ProviderEncryptionError("PROVIDER_ENCRYPTION_KEY is not a valid Fernet key.") from exc


def _decrypt(value: str | None, settings: ProviderSettings) -> str | None:
    if not value or not value.startswith(_ENCRYPTED_PREFIX):
        # Backward compatibility: legacy database values were stored as plaintext.
        return value
    try:
        return _fernet(settings).decrypt(value[len(_ENCRYPTED_PREFIX) :].encode()).decode()
    except InvalidToken as exc:
        raise ProviderEncryptionError("Stored provider key cannot be decrypted.") from exc


def _encrypt(value: str | None, settings: ProviderSettings) -> str | None:
    if not value:
        return None
    return _ENCRYPTED_PREFIX + _fernet(settings).encrypt(value.encode()).decode()


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


def _row_to_config(row: ProviderConfig, settings: ProviderSettings) -> ProvidersConfig:
    return ProvidersConfig(
        chat=ChatProviderConfig(
            provider=row.chat_provider,
            base_url=row.chat_base_url,
            api_key=_decrypt(row.chat_api_key_encrypted, settings),
            model=row.chat_model,
        ),
        embedding=EmbeddingProviderConfig(
            provider=row.embedding_provider,
            base_url=row.embedding_base_url,
            api_key=_decrypt(row.embedding_api_key_encrypted, settings),
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
    return _row_to_config(row, settings)


def save_provider_config(
    db: Session,
    workspace_id: str,
    payload: ProvidersConfig,
    settings: ProviderSettings,
) -> ProvidersConfig:
    validate_provider_url(
        payload.chat.base_url,
        allow_private_network=getattr(settings, "allow_private_provider_urls", False),
    )
    validate_provider_url(
        payload.embedding.base_url,
        allow_private_network=getattr(settings, "allow_private_provider_urls", False),
    )
    validate_provider_url(
        payload.embedding.huggingface_endpoint,
        allow_private_network=getattr(settings, "allow_private_provider_urls", False),
    )
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
    chat_key = (
        None
        if payload.chat.clear_api_key
        else current.chat.api_key
        if is_masked(payload.chat.api_key)
        else payload.chat.api_key
    )
    row.chat_api_key_encrypted = _encrypt(chat_key, settings)
    row.chat_model = payload.chat.model
    row.embedding_provider = payload.embedding.provider
    row.embedding_base_url = payload.embedding.base_url
    embedding_key = (
        None
        if payload.embedding.clear_api_key
        else current.embedding.api_key
        if is_masked(payload.embedding.api_key)
        else payload.embedding.api_key
    )
    row.embedding_api_key_encrypted = _encrypt(embedding_key, settings)
    row.embedding_model = payload.embedding.model
    row.huggingface_endpoint = payload.embedding.huggingface_endpoint

    db.commit()
    db.refresh(row)
    return _row_to_config(row, settings)
