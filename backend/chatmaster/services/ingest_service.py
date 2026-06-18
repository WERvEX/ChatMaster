"""Ingestion: load -> chunk -> embed -> upsert. Shared by the CLI and web upload."""

from __future__ import annotations

from pathlib import Path

from chatmaster.ai.chunkers import split_documents
from chatmaster.ai.loaders import UnsupportedFileType, load_file
from chatmaster.ai.models import build_embeddings
from chatmaster.ai.vectorstore import get_store
from chatmaster.config import get_settings
from chatmaster.identities.loader import get_registry
from chatmaster.schemas.api import IngestFileResult, IngestResult


def ingest(
    identity_id: str,
    files: list[Path],
    target: str = "private",
) -> IngestResult:
    """Ingest files into the identity's private collection or the common one.

    `target` is "private" (identity.private_collection) or "common" (COMMON_COLLECTION).
    """
    settings = get_settings()
    registry = get_registry()
    identity = registry.get(identity_id)  # raises IdentityNotFound if missing

    collection = (
        settings.common_collection if target == "common" else identity.private_collection
    )
    embeddings = build_embeddings(identity)
    store = get_store(collection, embeddings)

    file_results: list[IngestFileResult] = []
    total_chunks = 0

    for path in files:
        try:
            docs = load_file(path, identity_id=identity_id)
            chunks = split_documents(docs)
            if chunks:
                store.add_documents(chunks)
            file_results.append(IngestFileResult(file=path.name, chunks=len(chunks)))
            total_chunks += len(chunks)
        except UnsupportedFileType as e:
            file_results.append(IngestFileResult(file=path.name, error=str(e)))
        except Exception as e:  # noqa: BLE001
            file_results.append(IngestFileResult(file=path.name, error=f"{type(e).__name__}: {e}"))

    return IngestResult(
        identity_id=identity_id,
        target=target,
        collection=collection,
        files=file_results,
        total_chunks=total_chunks,
    )
