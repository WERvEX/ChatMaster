"""FastAPI app factory with lifespan that validates identities and ensures collections."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

# Force the HuggingFace download mirror BEFORE any library that transitively
# imports huggingface_hub (langchain-huggingface / sentence-transformers) gets
# imported. huggingface_hub caches its endpoint constant at import time, so
# setting it later inside a function is too late — the official huggingface.co
# would be used and time out in regions without direct access. This default can
# be overridden by an explicit HF_ENDPOINT in the environment / .env.
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chatmaster.config import get_settings
from chatmaster.routers import chat, conversations, documents, health, identities, providers

logger = logging.getLogger("chatmaster")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    from chatmaster.db.init_db import migrate_db
    from chatmaster.db.seed import seed_local_data
    from chatmaster.db.session import SessionLocal

    migrate_db()
    with SessionLocal() as db:
        seed_local_data(db, settings)
        from sqlalchemy import update

        from chatmaster.db.models import Message

        db.execute(
            update(Message)
            .where(Message.role == "assistant", Message.status == "pending")
            .values(status="stopped")
        )
        db.commit()
    with SessionLocal() as db:
        from chatmaster.identities.service import list_identity_models

        identity_ids = [
            item.id
            for item in list_identity_models(
                db,
                workspace_id=settings.local_workspace_id,
                include_archived=True,
            )
        ]
    logger.info("Identities: %s", identity_ids)
    from chatmaster.documents.jobs import resume_pending_jobs

    resumed = resume_pending_jobs()
    logger.info("ChatMaster ready. Resumed ingest jobs: %s", resumed)

    try:
        yield
    finally:
        from chatmaster.ai.vectorstore import close_clients
        from chatmaster.documents.jobs import shutdown_jobs

        shutdown_jobs()
        close_clients()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ChatMaster", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(identities.router)
    app.include_router(conversations.router)
    app.include_router(chat.router)
    app.include_router(documents.router)
    app.include_router(providers.router)
    return app


app = create_app()
