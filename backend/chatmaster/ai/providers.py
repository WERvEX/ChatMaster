"""Runtime-customizable provider configuration.

Users edit the chat + embedding provider settings (base_url, api_key, model)
from the web UI "API 配置" page. The config persists to a JSON file
(``Settings.providers_file``); the ``.env`` / :class:`Settings` values act as
the seed defaults on first run. This replaces the old hardcoded
``if provider == "openai"/"anthropic"/"huggingface"`` branches in
``models.py`` — that module now reads from :func:`get_provider_config` here.
"""

from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from chatmaster.config import get_settings

_LOCK = threading.Lock()

# Mask sentinel embedded in masked keys (see :func:`mask_key`).
_MASK_TOKEN = "****"


class ChatProviderConfig(BaseModel):
    """The active chat (generation) provider. OpenAI-compatible or Anthropic."""

    provider: str = "openai"  # openai | anthropic  (openai covers DeepSeek/Moonshot/...)
    base_url: str | None = None  # None => library default (OpenAI). DeepSeek: https://api.deepseek.com/v1
    api_key: str | None = None
    model: str = "deepseek-v4-pro"


class EmbeddingProviderConfig(BaseModel):
    """The active embedding provider. Local HuggingFace (default) or OpenAI-compatible."""

    provider: str = "huggingface"  # huggingface | openai
    base_url: str | None = None  # only used for openai-compatible embeddings
    api_key: str | None = None
    model: str = "BAAI/bge-small-zh-v1.5"
    huggingface_endpoint: str | None = "https://hf-mirror.com"  # HF download mirror


class ProvidersConfig(BaseModel):
    chat: ChatProviderConfig
    embedding: EmbeddingProviderConfig


def providers_path() -> Path:
    return Path(get_settings().providers_file)


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
def get_provider_config() -> ProvidersConfig:
    """Return the active provider config.

    Loads from the persisted JSON file; falls back to the ``.env`` seed if the
    file is missing or corrupt. The result is cached — call
    :func:`save_provider_config` (which clears the cache) after edits.
    """
    path = providers_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ProvidersConfig.model_validate(data)
        except Exception:
            # Corrupt/unreadable file -> fall back to seed rather than crash.
            pass
    return seed_from_settings()


def save_provider_config(cfg: ProvidersConfig) -> ProvidersConfig:
    """Persist ``cfg`` to disk and invalidate all downstream caches."""
    path = providers_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        path.write_text(cfg.model_dump_json(indent=2), encoding="utf-8")
    get_provider_config.cache_clear()

    # The model/embedding builders cache instances by (model, base_url, key);
    # new credentials/model must take effect immediately.
    from chatmaster.ai import models as _models

    _models.clear_caches()
    return get_provider_config()


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
