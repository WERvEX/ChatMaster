from __future__ import annotations

import pytest
from langchain_core.documents import Document

from chatmaster.retrieval.schemas import SearchHit
from chatmaster.retrieval.vectorstore import VectorDimensionMismatch, validate_vector_dimension


def _hit(text: str, collection: str, rank: int, score: float, point_id: str | None = None) -> SearchHit:
    return SearchHit(
        document=Document(
            page_content=text,
            metadata={"source_file": f"{text}.txt", "_id": point_id or text},
        ),
        collection=collection,
        rank=rank,
        dense_score=score,
    )


def test_weighted_rrf_orders_private_and_common_results() -> None:
    from chatmaster.retrieval.retriever import fuse_ranked_results

    chunks = fuse_ranked_results(
        private_hits=[_hit("private-a", "private", 1, 0.92)],
        common_hits=[_hit("common-a", "common", 1, 0.95)],
        top_k=2,
        private_weight=0.8,
        common_weight=0.2,
        min_chunks_common=0,
        common_collection="common",
    )

    assert [c.text for c in chunks] == ["private-a", "common-a"]
    assert chunks[0].fusion_score > chunks[1].fusion_score


def test_min_chunks_common_is_enforced_in_final_top_k() -> None:
    from chatmaster.retrieval.retriever import fuse_ranked_results

    chunks = fuse_ranked_results(
        private_hits=[
            _hit("private-a", "private", 1, 0.99),
            _hit("private-b", "private", 2, 0.98),
            _hit("private-c", "private", 3, 0.97),
        ],
        common_hits=[_hit("common-a", "common", 1, 0.5)],
        top_k=2,
        private_weight=0.9,
        common_weight=0.1,
        min_chunks_common=1,
        common_collection="common",
    )

    assert len(chunks) == 2
    assert sum(1 for c in chunks if c.collection == "common") == 1


def test_duplicate_chunks_are_fused_by_stable_id() -> None:
    from chatmaster.retrieval.retriever import fuse_ranked_results

    chunks = fuse_ranked_results(
        private_hits=[_hit("same", "private", 1, 0.91, point_id="chunk-1")],
        common_hits=[_hit("same", "common", 1, 0.88, point_id="chunk-1")],
        top_k=3,
        private_weight=0.6,
        common_weight=0.4,
        min_chunks_common=0,
        common_collection="common",
    )

    assert len(chunks) == 1
    assert chunks[0].fusion_score > 0.6 / 61


def test_validate_vector_dimension_raises_clear_error_on_mismatch() -> None:
    with pytest.raises(VectorDimensionMismatch, match="expected 512"):
        validate_vector_dimension("chatmaster_legal_expert", expected_dim=512, actual_dim=1536)
