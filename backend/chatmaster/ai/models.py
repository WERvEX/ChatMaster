"""Factory: build LangChain chat models and embeddings from provider config.

The active provider config (chat base_url/api_key/model + embedding provider)
is user-editable at runtime from the web UI "API 配置" page and lives in
``chatmaster.ai.providers``. This module is the single place that knows which
concrete LangChain class to instantiate for a given provider *type*.

Chat: OpenAI-compatible (DeepSeek / OpenAI / Moonshot / ...) or Anthropic.
Embeddings: local HuggingFace (default, free, no API key) or OpenAI-compatible.
"""

from __future__ import annotations

import os
from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from chatmaster.ai.providers import get_provider_config
from chatmaster.config import get_settings
from chatmaster.identities.schema import IdentityConfig
from chatmaster.providers.security import validate_provider_url

# Provider type aliases that all speak the OpenAI chat/embeddings protocol.
_OPENAI_COMPATIBLE = {"openai", "deepseek", "moonshot", "openai-compatible"}


# ----- Chat models -----


@lru_cache(maxsize=64)
def _build_openai_chat(model: str, base_url: str | None, api_key: str) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    kwargs: dict = {"model": model, "streaming": True, "api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


@lru_cache(maxsize=64)
def _build_anthropic_chat(model: str, api_key: str) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model, streaming=True, api_key=api_key)


def build_chat_model(identity: IdentityConfig) -> BaseChatModel:
    """Return a cached, streaming BaseChatModel for the identity's provider/model.

    The provider type, base_url, and api_key come from the runtime provider
    config (editable from the UI). An identity may override only the model name
    via ``generation_model``.
    """
    cfg = get_provider_config().chat
    settings = get_settings()
    model = identity.generation_model or cfg.model
    provider = cfg.provider.lower()
    # .env value still works as a fallback if the UI config has no key set.
    api_key = cfg.api_key or settings.openai_api_key
    base_url = cfg.base_url or settings.openai_base_url
    validate_provider_url(base_url, allow_private_network=settings.allow_private_provider_urls)

    if provider in _OPENAI_COMPATIBLE:
        if not api_key:
            raise RuntimeError(
                "Chat API key not configured. Set it on the API 配置 page "
                "(or OPENAI_API_KEY in .env)."
            )
        return _build_openai_chat(model, base_url, api_key)
    if provider == "anthropic":
        if not api_key:
            raise RuntimeError("Anthropic API key not configured. Set it on the API 配置 page.")
        return _build_anthropic_chat(model, api_key)
    raise ValueError(f"Unknown chat provider: {provider}")


# ----- Embeddings -----


@lru_cache(maxsize=8)
def _build_hf_embeddings(model: str, endpoint: str | None) -> Embeddings:
    # Apply HF mirror before the library loads any model.
    if endpoint:
        os.environ["HF_ENDPOINT"] = endpoint
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=model,
        encode_kwargs={"normalize_embeddings": True},
    )


@lru_cache(maxsize=8)
def _build_openai_embeddings(model: str, base_url: str | None, api_key: str) -> Embeddings:
    from langchain_openai import OpenAIEmbeddings

    kwargs: dict = {"model": model, "api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAIEmbeddings(**kwargs)


def build_embeddings(identity: IdentityConfig | None = None) -> Embeddings:
    """Build the embeddings model from the runtime provider config.

    - provider "huggingface" (default): free, local, no API key. Good for Chinese.
    - provider "openai": OpenAI-compatible embeddings (needs a key + endpoint).
    An identity may override the model name via ``embedding_model``.
    """
    cfg = get_provider_config().embedding
    settings = get_settings()
    model = identity.embedding_model if identity and identity.embedding_model else cfg.model
    provider = cfg.provider.lower()

    if provider == "huggingface":
        return _build_hf_embeddings(model, cfg.huggingface_endpoint)
    if provider in _OPENAI_COMPATIBLE:
        api_key = cfg.api_key or settings.openai_api_key
        base_url = cfg.base_url or settings.openai_base_url
        validate_provider_url(base_url, allow_private_network=settings.allow_private_provider_urls)
        if not api_key:
            raise RuntimeError("Embedding API key not configured. Set it on the API 配置 page.")
        return _build_openai_embeddings(model, base_url, api_key)
    raise ValueError(f"Unknown embedding provider: {provider}")


def clear_caches() -> None:
    """Invalidate all cached model/embedding instances.

    Called after the user saves new provider config so the next build picks up
    the new credentials/model/base_url.
    """
    _build_openai_chat.cache_clear()
    _build_anthropic_chat.cache_clear()
    _build_hf_embeddings.cache_clear()
    _build_openai_embeddings.cache_clear()

    # Cached vector stores hold a reference to the old embeddings object; drop
    # them so the next retrieve() binds the new embeddings.
    from chatmaster.ai.vectorstore import clear_store_cache

    clear_store_cache()
