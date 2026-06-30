"""Provider configuration endpoints — the backend of the "API 配置" page.

GET  /api/providers       → current config (api_keys masked) for the form
PUT  /api/providers       → persist edited config (keeps existing key if the
                            submitted value is empty or a mask)
POST /api/providers/test  → smoke-test the configured chat + embedding providers
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from chatmaster.ai.models import build_chat_model, build_embeddings
from chatmaster.ai.providers import (
    ProvidersConfig,
    get_provider_config,
    is_masked,
    mask_key,
    save_provider_config,
)
from chatmaster.core.auth import get_current_workspace_id
from chatmaster.identities.loader import get_registry
from chatmaster.identities.schema import IdentityConfig, RetrievalConfig

router = APIRouter(prefix="/api/providers", tags=["providers"])


def _masked(cfg: ProvidersConfig) -> dict:
    """Project the config for the UI, masking both API keys."""
    return {
        "chat": {
            "provider": cfg.chat.provider,
            "base_url": cfg.chat.base_url,
            "api_key": mask_key(cfg.chat.api_key),
            "model": cfg.chat.model,
        },
        "embedding": {
            "provider": cfg.embedding.provider,
            "base_url": cfg.embedding.base_url,
            "api_key": mask_key(cfg.embedding.api_key),
            "model": cfg.embedding.model,
            "huggingface_endpoint": cfg.embedding.huggingface_endpoint,
        },
    }


@router.get("")
async def get_providers(workspace_id: str = Depends(get_current_workspace_id)):
    _ = workspace_id
    return _masked(get_provider_config())


@router.put("")
async def update_providers(
    payload: ProvidersConfig,
    workspace_id: str = Depends(get_current_workspace_id),
):
    _ = workspace_id
    current = get_provider_config()
    # If the UI sent back the masked key (or an empty string), keep the stored
    # key instead of overwriting it with the mask.
    if is_masked(payload.chat.api_key):
        payload.chat.api_key = current.chat.api_key
    if is_masked(payload.embedding.api_key):
        payload.embedding.api_key = current.embedding.api_key
    saved = save_provider_config(payload)
    return _masked(saved)


class ProviderTestResult(BaseModel):
    chat: str  # "ok" or an error message
    embedding: str


@router.post("/test", response_model=ProviderTestResult)
async def test_providers(workspace_id: str = Depends(get_current_workspace_id)):
    _ = workspace_id
    """Smoke-test the currently saved chat + embedding providers.

    Runs the (synchronous) LangChain calls in a threadpool so the event loop
    is not blocked. Each side is independent — an embedding failure still
    reports the chat result.
    """
    # Use a throwaway identity shell so build_chat_model/build_embeddings apply
    # their identity-override defaults (none here → uses provider config).
    dummy = IdentityConfig(
        id="__provider_test__",
        name="test",
        description="",
        system_prompt="",
        private_collection="",
        retrieval=RetrievalConfig(),
    )

    def _test_chat() -> str:
        try:
            from langchain_core.messages import HumanMessage

            model = build_chat_model(dummy)
            model.invoke([HumanMessage(content="ping")])
            return "ok"
        except Exception as e:  # noqa: BLE001 — surface any failure to the UI
            return f"{type(e).__name__}: {e}"

    def _test_embedding() -> str:
        try:
            emb = build_embeddings()
            vec = emb.embed_query("dimension probe")
            return f"ok (dim={len(vec)})"
        except Exception as e:  # noqa: BLE001
            return f"{type(e).__name__}: {e}"

    chat_result, emb_result = await run_in_threadpool(_test_chat), await run_in_threadpool(_test_embedding)
    return ProviderTestResult(chat=chat_result, embedding=emb_result)
