"""Document persistence plus synchronous ingestion for the local MVP."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from chatmaster.ai.loaders import SUPPORTED_EXTENSIONS
from chatmaster.db.models import Document, IngestJob
from chatmaster.schemas.api import IngestFileResult
from chatmaster.services.ingest_service import ingest


class UnsupportedDocumentType(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _default_ingest(identity_id: str, paths: list[Path], target: str) -> int:
    result = ingest(identity_id, paths, target=target)
    return result.total_chunks


def _document_namespace(target: str) -> str:
    return "common" if target == "common" else "private"


def ingest_uploaded_document(
    *,
    db: Session,
    workspace_id: str,
    identity_id: str,
    target: str,
    filename: str,
    content_type: str | None,
    data: bytes,
    storage_dir: str | Path,
    ingest_func: Callable[[str, list[Path], str], int] = _default_ingest,
) -> IngestFileResult:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentType(f"Unsupported file type: {filename}")

    namespace = _document_namespace(target)
    document_id = str(uuid.uuid4())
    storage_root = Path(storage_dir)
    document_dir = storage_root / workspace_id / "documents" / document_id
    document_dir.mkdir(parents=True, exist_ok=True)
    destination = document_dir / filename
    destination.write_bytes(data)

    identity_for_document = None if namespace == "common" else identity_id
    document = Document(
        id=document_id,
        workspace_id=workspace_id,
        identity_id=identity_for_document,
        namespace=namespace,
        filename=filename,
        content_type=content_type,
        storage_path=str(destination),
        sha256=_sha256(data),
        status="ingesting",
    )
    job = IngestJob(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        document_id=document_id,
        status="running",
        error=None,
        total_chunks=0,
    )
    db.add_all([document, job])
    db.commit()

    try:
        total_chunks = ingest_func(identity_id, [destination], target)
    except Exception as exc:  # noqa: BLE001 - record ingestion failures per file
        error = f"{type(exc).__name__}: {exc}"
        document.status = "failed"
        job.status = "failed"
        job.error = error
        db.commit()
        return IngestFileResult(file=filename, chunks=0, error=error)

    document.status = "indexed"
    job.status = "completed"
    job.total_chunks = total_chunks
    db.commit()
    return IngestFileResult(file=filename, chunks=total_chunks)


def list_documents(
    db: Session,
    *,
    workspace_id: str,
    identity_id: str | None = None,
    namespace: str | None = None,
    status: str | None = None,
) -> list[Document]:
    stmt = select(Document).where(Document.workspace_id == workspace_id)
    if identity_id:
        stmt = stmt.where(Document.identity_id == identity_id)
    if namespace:
        stmt = stmt.where(Document.namespace == namespace)
    if status:
        stmt = stmt.where(Document.status == status)
    return list(db.execute(stmt.order_by(Document.created_at.desc())).scalars())


def list_ingest_jobs(
    db: Session,
    *,
    workspace_id: str,
    status: str | None = None,
) -> list[IngestJob]:
    stmt = select(IngestJob).where(IngestJob.workspace_id == workspace_id)
    if status:
        stmt = stmt.where(IngestJob.status == status)
    return list(db.execute(stmt.order_by(IngestJob.created_at.desc())).scalars())
