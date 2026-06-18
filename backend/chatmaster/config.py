"""Application settings, loaded from environment / .env via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    # ---- LLM (OpenAI-compatible) ----
    # DeepSeek / OpenAI / Moonshot / etc. all speak the OpenAI chat protocol.
    # For DeepSeek: OPENAI_BASE_URL=https://api.deepseek.com/v1, model=deepseek-v4-pro
    openai_api_key: str | None = None
    openai_base_url: str | None = None  # None => default https://api.openai.com/v1
    anthropic_api_key: str | None = None

    # Which chat provider to use when an identity does not override llm_provider.
    default_llm_provider: str = "openai"  # openai | anthropic
    default_generation_model: str = "deepseek-v4-pro"

    # ---- Embeddings ----
    # DeepSeek has no embeddings API, so we default to a local HuggingFace model.
    # Supported: "huggingface" (local, free) | "openai"
    default_embedding_provider: str = "huggingface"
    default_embedding_model: str = "BAAI/bge-small-zh-v1.5"
    # HuggingFace download mirror (helpful in China). Set to https://hf-mirror.com
    huggingface_endpoint: str | None = "https://hf-mirror.com"

    # Runtime-customizable provider config (edited from the web UI "API 配置" page).
    # On first run, if this file is absent it is seeded from the .env values above.
    providers_file: str = "data/providers.json"

    # RAG
    common_collection: str = "chatmaster_common"
    common_top_k: int = 4
    chunk_size: int = 800
    chunk_overlap: int = 120

    # Server. Env value is a JSON array string, e.g. ["http://localhost:5173"]
    cors_origins: list[str] = ["http://localhost:5173"]
    upload_max_bytes: int = 26 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Clear the cache and return fresh settings (useful in tests)."""
    get_settings.cache_clear()
    return get_settings()
