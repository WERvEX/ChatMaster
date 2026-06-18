"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from chatmaster.ai.providers import get_provider_config
from chatmaster.config import get_settings
from chatmaster.identities.loader import get_registry

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    cfg = get_provider_config()
    registry = get_registry()
    return {
        "status": "ok",
        "providers": {
            "chat": {
                "provider": cfg.chat.provider,
                "model": cfg.chat.model,
                "base_url": cfg.chat.base_url,
                "configured": bool(cfg.chat.api_key),
            },
            "embedding": {
                "provider": cfg.embedding.provider,
                "model": cfg.embedding.model,
                "configured": True,
            },
        },
        "collections": registry.all_collections() + [get_settings().common_collection],
        "identities": [i.id for i in registry.list_all()],
    }
