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
from chatmaster.identities.loader import get_registry
from chatmaster.routers import chat, documents, health, identities, providers

logger = logging.getLogger("chatmaster")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    from chatmaster.db.init_db import init_db
    from chatmaster.db.seed import seed_local_data
    from chatmaster.db.session import SessionLocal

    init_db()
    with SessionLocal() as db:
        seed_local_data(db, settings)
    registry = get_registry()  # validates identities.yaml, fails fast on typos

    # Determine embedding dimension for the default embedding model.
    from chatmaster.ai.models import build_embeddings

    embeddings = build_embeddings()
    dim = len(embeddings.embed_query("dimension probe"))

    # Ensure every private collection + the common collection exist.
    from chatmaster.ai.vectorstore import ensure_all_collections

    names = ensure_all_collections(
        registry.all_collections(), settings.common_collection, dim
    )
    logger.info("ChatMaster ready. Collections ensured: %s", names)
    logger.info("Identities: %s", [i.id for i in registry.list_all()])

    yield


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
    app.include_router(chat.router)
    app.include_router(documents.router)
    app.include_router(providers.router)
    return app


app = create_app()
