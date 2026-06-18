"""Pydantic schemas for identity configuration (loaded from identities.yaml)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievalConfig(BaseModel):
    """How an identity retrieves context from its private + the common collection."""

    top_k: int = 6
    private_weight: float = 0.6
    common_weight: float = 0.4
    min_chunks_common: int = 2


class IdentityConfig(BaseModel):
    """A single chat identity / persona, fully driven by config."""

    id: str = Field(..., description="Slug, e.g. legal_expert")
    name: str
    description: str
    system_prompt: str
    private_collection: str
    llm_provider: str | None = None  # falls back to DEFAULT_LLM_PROVIDER
    embedding_model: str | None = None  # falls back to DEFAULT_EMBEDDING_MODEL
    generation_model: str | None = None  # falls back to DEFAULT_GENERATION_MODEL
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)


class IdentityOut(BaseModel):
    """Public-facing projection of an identity (no system prompt leaked)."""

    id: str
    name: str
    description: str
    generation_model: str | None
    retrieval: RetrievalConfig
