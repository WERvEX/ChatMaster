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
_CLIENT_LOCK = threading.Lock()
_CLIENT_CACHE: dict[tuple[str, str | None], object] = {}


def _client():
    """Return a process-wide Qdrant client for the active connection settings.

    A local ``:memory:`` Qdrant instance lives inside one client object. Creating
    a fresh client for each operation therefore made collection creation, ingest,
    and search talk to different empty databases in tests and local development.
    """
    from qdrant_client import QdrantClient

    s = get_settings()
    key = (s.qdrant_url, s.qdrant_api_key or None)
    with _CLIENT_LOCK:
        client = _CLIENT_CACHE.get(key)
        if client is None:
            # ":memory:" is supported by qdrant-client for tests/dev (no persistence).
            client = (
                QdrantClient(location=":memory:")
                if s.qdrant_url == ":memory:"
                else QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key or None)
            )
            _CLIENT_CACHE[key] = client
        return client


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
    model_key = f"{type(embeddings).__module__}.{type(embeddings).__qualname__}:" + str(
        getattr(embeddings, "model_name", getattr(embeddings, "model", "default"))
    )
    key = (collection, model_key)
    with _STORE_LOCK:
        store = _STORE_CACHE.get(key)
        if store is None:
            # Validate at the point of use as provider settings can change at
            # runtime after application startup. This turns an opaque Qdrant
            # write/search failure into a clear rebuild-required error.
            dim = len(embeddings.embed_query("dimension probe"))
            ensure_collection(collection, dim)
            store = _get_store(collection, model_key, embeddings)
            _STORE_CACHE[key] = store
        return store


def clear_store_cache() -> None:
    """Drop cached stores (call after provider/embedding config changes so new
    embeddings take effect)."""
    with _STORE_LOCK:
        _STORE_CACHE.clear()


def close_clients() -> None:
    """Close and discard cached clients (primarily used during application shutdown)."""
    with _CLIENT_LOCK:
        clients = list(_CLIENT_CACHE.values())
        _CLIENT_CACHE.clear()
    for client in clients:
        close = getattr(client, "close", None)
        if close is not None:
            close()


def delete_collection(name: str) -> None:
    """Delete a physical collection; callers must require explicit confirmation."""
    client = _client()
    existing = {collection.name for collection in client.get_collections().collections}
    if name in existing:
        client.delete_collection(name)
    with _STORE_LOCK:
        for key in [key for key in _STORE_CACHE if key[0] == name]:
            del _STORE_CACHE[key]


def delete_points(collection: str, point_ids: list[str]) -> None:
    if not point_ids:
        return
    from qdrant_client.http.models import PointIdsList

    _client().delete(
        collection_name=collection,
        points_selector=PointIdsList(points=point_ids),
        wait=True,
    )


def ensure_all_collections(
    private_collections: list[str], common_collection: str, dim: int
) -> list[str]:
    """Create every collection the app needs. Returns the list created/ensured."""
    names = [*private_collections, common_collection]
    for name in names:
        ensure_collection(name, dim)
    return names
