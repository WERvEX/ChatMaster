from __future__ import annotations

import pytest


def test_memory_qdrant_client_is_shared_between_collection_operations(monkeypatch) -> None:
    from chatmaster.ai import vectorstore

    class Settings:
        qdrant_url = ":memory:"
        qdrant_api_key = None

    monkeypatch.setattr(vectorstore, "get_settings", lambda: Settings())
    vectorstore.close_clients()
    try:
        vectorstore.ensure_collection("test_shared_memory", 3)
        names = {item.name for item in vectorstore._client().get_collections().collections}
        assert "test_shared_memory" in names
    finally:
        vectorstore.close_clients()


def test_get_store_rejects_existing_collection_with_wrong_embedding_dimension(monkeypatch) -> None:
    from chatmaster.ai import vectorstore
    from chatmaster.retrieval.vectorstore import VectorDimensionMismatch

    class Settings:
        qdrant_url = ":memory:"
        qdrant_api_key = None

    class Embeddings:
        model_name = "test-model"

        def embed_query(self, _text):
            return [0.0, 0.0, 0.0, 0.0]

    monkeypatch.setattr(vectorstore, "get_settings", lambda: Settings())
    vectorstore.close_clients()
    vectorstore.clear_store_cache()
    try:
        vectorstore.ensure_collection("test_dimension_guard", 3)
        with pytest.raises(VectorDimensionMismatch, match="Rebuild the index"):
            vectorstore.get_store("test_dimension_guard", Embeddings())
    finally:
        vectorstore.clear_store_cache()
        vectorstore.close_clients()
