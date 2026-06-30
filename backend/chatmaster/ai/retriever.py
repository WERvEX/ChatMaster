"""Compatibility wrapper for the retrieval package."""

from __future__ import annotations

from langchain_core.embeddings import Embeddings

from chatmaster.identities.schema import IdentityConfig
from chatmaster.retrieval.retriever import retrieve as _retrieve
from chatmaster.retrieval.schemas import RetrievedChunk


async def retrieve(
    identity: IdentityConfig,
    query: str,
    embeddings: Embeddings,
) -> list[RetrievedChunk]:
    return await _retrieve(identity, query, embeddings)
