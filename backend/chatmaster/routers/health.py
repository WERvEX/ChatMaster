"""Liveness and dependency-aware health endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select, text

from chatmaster.ai.providers import get_provider_config
from chatmaster.db.models import Identity, IndexVersion
from chatmaster.db.session import SessionLocal

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/live")
async def live():
    return {"status": "ok"}


@router.get("/health")
async def health():
    checks: dict[str, dict] = {}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            stale = db.scalars(
                select(IndexVersion.id).where(IndexVersion.status == "stale")
            ).first()
            identity_ids = list(
                db.scalars(
                    select(Identity.id).where(
                        Identity.is_active.is_(True),
                    )
                )
            )
        checks["database"] = {"status": "ok"}
        checks["indexes"] = {
            "status": "degraded" if stale else "ok",
            "message": "rebuild required" if stale else None,
        }
    except Exception as exc:  # noqa: BLE001
        checks["database"] = {"status": "degraded", "message": type(exc).__name__}

    try:
        from chatmaster.ai.vectorstore import _client

        collections = [item.name for item in _client().get_collections().collections]
        checks["qdrant"] = {"status": "ok", "collections": collections}
    except Exception as exc:  # noqa: BLE001
        checks["qdrant"] = {"status": "degraded", "message": type(exc).__name__}

    cfg = get_provider_config()
    chat_configured = bool(cfg.chat.api_key)
    embedding_configured = cfg.embedding.provider == "huggingface" or bool(cfg.embedding.api_key)
    checks["providers"] = {
        "status": "ok" if chat_configured and embedding_configured else "degraded",
        "chat_configured": chat_configured,
        "embedding_configured": embedding_configured,
    }
    overall = "ok" if all(check.get("status") == "ok" for check in checks.values()) else "degraded"
    return {
        "status": overall,
        "checks": checks,
        "identities": identity_ids if "identity_ids" in locals() else [],
    }
