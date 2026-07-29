"""Private/common retrieval with weighted RRF fusion."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from sqlalchemy.orm import Session

from chatmaster.ai.vectorstore import get_store
from chatmaster.config import get_settings
from chatmaster.identities.schema import IdentityConfig
from chatmaster.retrieval.schemas import RetrievedChunk, SearchHit
from chatmaster.retrieval.indexes import active_collection, assert_indexes_fresh

_RRF_K = 60


def _doc_key(doc: Document) -> str:
    pid = doc.metadata.get("_id") or doc.metadata.get("id")
    if pid:
        return str(pid)
    return f"{doc.metadata.get('source_file', '')}::{hash(doc.page_content)}"


def _chunk_from_hit(
    hit: SearchHit,
    *,
    fusion_score: float,
) -> RetrievedChunk:
    metadata: dict[str, Any] = dict(hit.document.metadata)
    return RetrievedChunk(
        text=hit.document.page_content,
        source_file=metadata.get("source_file", "unknown"),
        collection=hit.collection,
        rank=hit.rank,
        dense_score=hit.dense_score,
        fusion_score=fusion_score,
        metadata=metadata,
    )


def fuse_ranked_results(
    *,
    private_hits: list[SearchHit],
    common_hits: list[SearchHit],
    top_k: int,
    private_weight: float,
    common_weight: float,
    min_chunks_common: int,
    common_collection: str,
) -> list[RetrievedChunk]:
    fused: dict[str, tuple[float, SearchHit]] = {}

    for hit in private_hits:
        key = _doc_key(hit.document)
        score = private_weight / (_RRF_K + hit.rank)
        previous = fused.get(key)
        fused[key] = ((previous[0] if previous else 0.0) + score, hit)

    for hit in common_hits:
        key = _doc_key(hit.document)
        score = common_weight / (_RRF_K + hit.rank)
        previous = fused.get(key)
        kept_hit = previous[1] if previous else hit
        fused[key] = ((previous[0] if previous else 0.0) + score, kept_hit)

    ranked = sorted(fused.values(), key=lambda item: item[0], reverse=True)
    selected = ranked[:top_k]

    common_count = sum(1 for _, hit in selected if hit.collection == common_collection)
    if common_count < min_chunks_common and common_hits:
        selected_keys = {_doc_key(hit.document) for _, hit in selected}
        needed = min_chunks_common - common_count
        extras: list[tuple[float, SearchHit]] = []
        for hit in common_hits:
            if _doc_key(hit.document) in selected_keys:
                continue
            extras.append((common_weight / (_RRF_K + hit.rank), hit))
            if len(extras) == needed:
                break
        if extras:
            keep_count = max(top_k - len(extras), 0)
            selected = selected[:keep_count] + extras
            selected.sort(key=lambda item: item[0], reverse=True)

    return [_chunk_from_hit(hit, fusion_score=score) for score, hit in selected[:top_k]]


async def _search_one(store, query: str, k: int, collection: str) -> list[SearchHit]:
    if hasattr(store, "asimilarity_search_with_score"):
        pairs = await store.asimilarity_search_with_score(query, k=k)
        return [
            SearchHit(document=doc, collection=collection, rank=index + 1, dense_score=score)
            for index, (doc, score) in enumerate(pairs)
        ]

    docs = await store.asimilarity_search(query, k=k)
    return [
        SearchHit(document=doc, collection=collection, rank=index + 1, dense_score=None)
        for index, doc in enumerate(docs)
    ]


async def retrieve(
    identity: IdentityConfig,
    query: str,
    embeddings: Embeddings,
    *,
    db: Session,
    workspace_id: str,
) -> list[RetrievedChunk]:
    settings = get_settings()
    cfg = identity.retrieval
    assert_indexes_fresh(db, workspace_id=workspace_id)

    private_collection = active_collection(
        db,
        workspace_id=workspace_id,
        logical_name=identity.private_collection,
        identity_id=identity.id,
    )
    common_collection = active_collection(
        db,
        workspace_id=workspace_id,
        logical_name=settings.common_collection,
        identity_id=None,
    )
    private_store = get_store(private_collection, embeddings)
    common_store = get_store(common_collection, embeddings)

    private_hits, common_hits = await asyncio.gather(
        _search_one(private_store, query, cfg.top_k, private_collection),
        _search_one(common_store, query, settings.common_top_k, common_collection),
    )

    return fuse_ranked_results(
        private_hits=private_hits,
        common_hits=common_hits,
        top_k=cfg.top_k,
        private_weight=cfg.private_weight,
        common_weight=cfg.common_weight,
        min_chunks_common=cfg.min_chunks_common,
        common_collection=common_collection,
    )
