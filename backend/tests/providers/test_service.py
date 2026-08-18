from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from chatmaster.ai.providers import (
    ChatProviderConfig,
    EmbeddingProviderConfig,
    ProvidersConfig,
)
from chatmaster.db.base import Base
from chatmaster.db.models import ProviderConfig, Workspace


class DummySettings:
    default_llm_provider = "openai"
    openai_base_url = "https://api.deepseek.com/v1"
    openai_api_key = "sk-original"
    default_generation_model = "deepseek-v4-pro"
    default_embedding_provider = "huggingface"
    default_embedding_model = "BAAI/bge-small-zh-v1.5"
    huggingface_endpoint = "https://hf-mirror.com"
    provider_encryption_key = "WlW2K8p6y83P8ueVBvjKqvPE9s2krJzRg3B9pFMn8Mk="
    allow_private_provider_urls = True


class PrivateBlockedSettings(DummySettings):
    allow_private_provider_urls = False


def _public_addresses(*items: str):
    return [(2, 1, 6, "", (item, 0)) for item in items]


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def test_get_provider_config_seeds_from_settings_when_missing() -> None:
    from chatmaster.providers.service import get_provider_config

    with _session() as db:
        db.add(Workspace(id="local", name="Local Workspace"))
        db.commit()

        cfg = get_provider_config(db, "local", DummySettings())

        assert cfg.chat.api_key == "sk-original"
        assert cfg.chat.model == "deepseek-v4-pro"
        assert cfg.embedding.provider == "huggingface"


def test_save_provider_config_replaces_new_keys(monkeypatch) -> None:
    from chatmaster.providers.service import get_provider_config, save_provider_config

    monkeypatch.setattr(
        "chatmaster.providers.security.socket.getaddrinfo",
        lambda *_: _public_addresses("93.184.216.34"),
    )
    with _session() as db:
        db.add(Workspace(id="local", name="Local Workspace"))
        db.commit()

        payload = ProvidersConfig(
            chat=ChatProviderConfig(
                provider="openai",
                base_url="https://api.example.com/v1",
                api_key="sk-new-chat",
                model="gpt-4o-mini",
            ),
            embedding=EmbeddingProviderConfig(
                provider="openai",
                base_url="https://api.example.com/v1",
                api_key="sk-new-embedding",
                model="text-embedding-3-small",
                huggingface_endpoint=None,
            ),
        )

        save_provider_config(db, "local", payload, DummySettings())
        saved = get_provider_config(db, "local", DummySettings())

        assert saved.chat.api_key == "sk-new-chat"
        assert saved.embedding.api_key == "sk-new-embedding"
        row = db.execute(select(ProviderConfig)).scalar_one()
        assert "sk-new-chat" not in row.chat_api_key_encrypted
        assert row.chat_api_key_encrypted.startswith("fernet:")


def test_save_provider_config_keeps_previous_keys_when_payload_is_masked(monkeypatch) -> None:
    from chatmaster.providers.service import get_provider_config, save_provider_config

    monkeypatch.setattr(
        "chatmaster.providers.security.socket.getaddrinfo",
        lambda *_: _public_addresses("93.184.216.34"),
    )
    with _session() as db:
        db.add(Workspace(id="local", name="Local Workspace"))
        db.commit()

        original = ProvidersConfig(
            chat=ChatProviderConfig(
                provider="openai",
                base_url="https://api.example.com/v1",
                api_key="sk-secret-chat",
                model="gpt-4o-mini",
            ),
            embedding=EmbeddingProviderConfig(
                provider="openai",
                base_url="https://api.example.com/v1",
                api_key="sk-secret-embedding",
                model="text-embedding-3-small",
                huggingface_endpoint=None,
            ),
        )
        save_provider_config(db, "local", original, DummySettings())

        masked = ProvidersConfig(
            chat=ChatProviderConfig(
                provider="openai",
                base_url="https://api.changed.com/v1",
                api_key="sk-****chat",
                model="gpt-4.1-mini",
            ),
            embedding=EmbeddingProviderConfig(
                provider="openai",
                base_url="https://api.changed.com/v1",
                api_key="sk-****ding",
                model="text-embedding-3-large",
                huggingface_endpoint=None,
            ),
        )
        save_provider_config(db, "local", masked, DummySettings())
        saved = get_provider_config(db, "local", DummySettings())

        assert saved.chat.api_key == "sk-secret-chat"
        assert saved.chat.base_url == "https://api.changed.com/v1"
        assert saved.embedding.api_key == "sk-secret-embedding"


def test_save_provider_config_validates_huggingface_endpoint(monkeypatch) -> None:
    from chatmaster.providers.security import UnsafeProviderUrl
    from chatmaster.providers.service import save_provider_config

    monkeypatch.setattr(
        "chatmaster.providers.security.socket.getaddrinfo",
        lambda *_: _public_addresses("192.168.1.20"),
    )
    payload = ProvidersConfig(
        chat=ChatProviderConfig(model="gpt-4o-mini"),
        embedding=EmbeddingProviderConfig(
            provider="huggingface",
            model="BAAI/bge-small-zh-v1.5",
            huggingface_endpoint="http://provider.test",
        ),
    )
    with _session() as db:
        db.add(Workspace(id="local", name="Local Workspace"))
        db.commit()
        with pytest.raises(UnsafeProviderUrl):
            save_provider_config(db, "local", payload, PrivateBlockedSettings())
