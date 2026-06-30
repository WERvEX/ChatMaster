from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from chatmaster.ai.providers import (
    ChatProviderConfig,
    EmbeddingProviderConfig,
    ProvidersConfig,
)
from chatmaster.db.base import Base
from chatmaster.db.models import Workspace


class DummySettings:
    default_llm_provider = "openai"
    openai_base_url = "https://api.deepseek.com/v1"
    openai_api_key = "sk-original"
    default_generation_model = "deepseek-v4-pro"
    default_embedding_provider = "huggingface"
    default_embedding_model = "BAAI/bge-small-zh-v1.5"
    huggingface_endpoint = "https://hf-mirror.com"


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


def test_save_provider_config_replaces_new_keys() -> None:
    from chatmaster.providers.service import get_provider_config, save_provider_config

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


def test_save_provider_config_keeps_previous_keys_when_payload_is_masked() -> None:
    from chatmaster.providers.service import get_provider_config, save_provider_config

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
