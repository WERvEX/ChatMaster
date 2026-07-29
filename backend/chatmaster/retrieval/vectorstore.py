"""Vector store helpers shared by retrieval and ingestion."""

from __future__ import annotations


class VectorDimensionMismatch(RuntimeError):
    pass


def validate_vector_dimension(collection_name: str, expected_dim: int, actual_dim: int) -> None:
    if expected_dim != actual_dim:
        raise VectorDimensionMismatch(
            f"Collection '{collection_name}' has vector size {actual_dim}; "
            f"expected {expected_dim}. Rebuild the index after changing the embedding model."
        )
