"""Qdrant vector store wrapper (langchain-qdrant).

Only this module talks to Qdrant. Reimplementing against another LangChain
VectorStore is how you'd swap the DB.
"""

from __future__ import annotations

import threading

from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore

from chatmaster.config import get_settings
from chatmaster.retrieval.vectorstore import validate_vector_dimension

# Cache QdrantVectorStore by (collection, model_key). We must NOT key on the
# embeddings object itself — Embeddings instances (e.g. HuggingFaceEmbeddings)
# are unhashable, which would raise "unhashable type: 'HuggingFaceEmbeddings'".
_STORE_LOCK = threading.Lock()
_STORE_CACHE: dict[tuple[str, str], QdrantVectorStore] = {}


def _client():
    """Build the underlying async-capable Qdrant client (shared across stores)."""
    from qdrant_client import QdrantClient

    s = get_settings()
    # ":memory:" is supported by qdrant-client for tests/dev (no persistence).
    if s.qdrant_url == ":memory:":
        return QdrantClient(location=":memory:")
    return QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key or None)


def ensure_collection(name: str, dim: int) -> None:
    """Idempotently create a collection with the given vector dimension."""
    from qdrant_client.http.models import Distance, VectorParams

    client = _client()
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        info = client.get_collection(name)
        vectors = info.config.params.vectors
        actual_dim = vectors.size if hasattr(vectors, "size") else int(vectors["size"])
        validate_vector_dimension(name, dim, actual_dim)
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )


def _get_store(collection: str, model_key: str, embeddings: Embeddings) -> QdrantVectorStore:
    client = _client()
    return QdrantVectorStore(
        client=client,
        collection_name=collection,
        embedding=embeddings,
    )


def get_store(collection: str, embeddings: Embeddings) -> QdrantVectorStore:
    """Return a cached QdrantVectorStore bound to a collection + embeddings."""
    model_key = str(getattr(embeddings, "model", "default"))
    key = (collection, model_key)
    with _STORE_LOCK:
        store = _STORE_CACHE.get(key)
        if store is None:
            store = _get_store(collection, model_key, embeddings)
            _STORE_CACHE[key] = store
        return store


def clear_store_cache() -> None:
    """Drop cached stores (call after provider/embedding config changes so new
    embeddings take effect)."""
    with _STORE_LOCK:
        _STORE_CACHE.clear()


def ensure_all_collections(
    private_collections: list[str], common_collection: str, dim: int
) -> list[str]:
    """Create every collection the app needs. Returns the list created/ensured."""
    names = [*private_collections, common_collection]
    for name in names:
        ensure_collection(name, dim)
    return names
