"""Hybrid retriever: query an identity's private collection AND the shared
common collection, then merge with weighted Reciprocal Rank Fusion (RRF).

Implemented as a plain async function (not a BaseRetriever subclass) for
clarity; the chain calls it directly. It can be wrapped in a BaseRetriever or
a LangGraph node later without changing the merge logic.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from chatmaster.ai.vectorstore import get_store
from chatmaster.config import get_settings
from chatmaster.identities.schema import IdentityConfig

# RRF constant. 60 is the conventional value from the original TREC paper.
_RRF_K = 60


@dataclass
class RetrievedChunk:
    text: str
    source_file: str
    collection: str
    score: float


def _doc_key(doc: Document) -> str:
    """Identity for a doc across the two result lists (used to fuse ranks)."""
    # Prefer the stored point id if present; fall back to content hash.
    pid = doc.metadata.get("_id") or doc.metadata.get("id")
    if pid:
        return f"{pid}"
    return f"{doc.metadata.get('source_file','')}::{hash(doc.page_content)}"


async def _search_one(
    store, query: str, k: int
) -> list[tuple[Document, int]]:
    """Return (doc, rank) pairs; rank starts at 1."""
    docs = await store.asimilarity_search(query, k=k)
    return [(d, i + 1) for i, d in enumerate(docs)]


async def retrieve(
    identity: IdentityConfig,
    query: str,
    embeddings: Embeddings,
) -> list[RetrievedChunk]:
    """Hybrid retrieve + weighted RRF merge of private + common collections."""
    settings = get_settings()
    cfg = identity.retrieval

    private_store = get_store(identity.private_collection, embeddings)
    common_store = get_store(settings.common_collection, embeddings)

    priv_results, common_results = await asyncio.gather(
        _search_one(private_store, query, cfg.top_k),
        _search_one(common_store, query, settings.common_top_k),
    )

    # Weighted RRF: score = w * 1/(k + rank). Absent from a list => 0 contribution.
    fused: dict[str, tuple[float, Document, str]] = {}
    for doc, rank in priv_results:
        key = _doc_key(doc)
        score = cfg.private_weight / (_RRF_K + rank)
        prev = fused.get(key)
        fused[key] = (
            (prev[0] if prev else 0.0) + score,
            doc,
            identity.private_collection,
        )
    for doc, rank in common_results:
        key = _doc_key(doc)
        score = cfg.common_weight / (_RRF_K + rank)
        prev = fused.get(key)
        prev_collection = prev[2] if prev else settings.common_collection
        fused[key] = (
            (prev[0] if prev else 0.0) + score,
            doc,
            prev_collection,
        )

    ranked = sorted(fused.values(), key=lambda x: x[0], reverse=True)

    # Bias: ensure at least min_chunks_common common chunks surface if available.
    selected: list[tuple[float, Document, str]] = []
    common_count = 0
    for score, doc, coll in ranked:
        selected.append((score, doc, coll))
        if coll == settings.common_collection:
            common_count += 1

    # If too few common chunks made the cut but some were retrieved, swap them in.
    if common_count < cfg.min_chunks_common and common_results:
        needed = cfg.min_chunks_common - common_count
        already_ids = {_doc_key(d) for _, d, _ in selected}
        extras = [
            (cfg.common_weight / (_RRF_K + rank), d, settings.common_collection)
            for d, rank in common_results
            if _doc_key(d) not in already_ids
        ][:needed]
        # Trim from the tail (lowest private scores) to make room.
        selected = selected[: cfg.top_k - len(extras)] + extras
        selected.sort(key=lambda x: x[0], reverse=True)

    return [
        RetrievedChunk(
            text=doc.page_content,
            source_file=doc.metadata.get("source_file", "unknown"),
            collection=coll,
            score=score,
        )
        for score, doc, coll in selected[: cfg.top_k]
    ]
