"""Document persistence plus synchronous ingestion for the local MVP."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from chatmaster.ai.loaders import SUPPORTED_EXTENSIONS
from chatmaster.db.models import Document, IngestJob
from chatmaster.identities.loader import get_registry
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


def _find_existing_document(
    db: Session,
    *,
    workspace_id: str,
    sha256: str,
    namespace: str,
    identity_id: str | None,
) -> Document | None:
    stmt = select(Document).where(
        Document.workspace_id == workspace_id,
        Document.sha256 == sha256,
        Document.namespace == namespace,
        Document.identity_id == identity_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def ingest_path_document(
    *,
    db: Session,
    workspace_id: str,
    identity_id: str,
    target: str,
    source_path: Path,
    filename: str | None = None,
    content_type: str | None = None,
    storage_dir: str | Path,
    ingest_func: Callable[[str, list[Path], str], int] = _default_ingest,
) -> IngestFileResult:
    get_registry().get(identity_id)

    path = Path(source_path)
    name = filename or path.name
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentType(f"Unsupported file type: {name}")

    namespace = _document_namespace(target)
    identity_for_document = None if namespace == "common" else identity_id
    file_bytes = path.read_bytes()
    digest = _sha256(file_bytes)

    existing = _find_existing_document(
        db,
        workspace_id=workspace_id,
        sha256=digest,
        namespace=namespace,
        identity_id=identity_for_document,
    )
    if existing is not None:
        if existing.status == "indexed":
            job = db.execute(
                select(IngestJob)
                .where(IngestJob.document_id == existing.id)
                .order_by(IngestJob.created_at.desc())
            ).scalar_one_or_none()
            chunks = job.total_chunks if job is not None else 0
            return IngestFileResult(file=name, chunks=chunks)
        document = existing
        document.status = "ingesting"
        job = IngestJob(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            document_id=document.id,
            status="running",
            error=None,
            total_chunks=0,
        )
        db.add(job)
        destination = Path(document.storage_path)
    else:
        document_id = str(uuid.uuid4())
        storage_root = Path(storage_dir)
        document_dir = storage_root / workspace_id / "documents" / document_id
        document_dir.mkdir(parents=True, exist_ok=True)
        destination = document_dir / name
        shutil.copy2(path, destination)
        document = Document(
            id=document_id,
            workspace_id=workspace_id,
            identity_id=identity_for_document,
            namespace=namespace,
            filename=name,
            content_type=content_type,
            storage_path=str(destination),
            sha256=digest,
            status="ingesting",
        )
        job = IngestJob(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            document_id=document.id,
            status="running",
            error=None,
            total_chunks=0,
        )
        db.add_all([document, job])

    db.commit()

    try:
        total_chunks = ingest_func(identity_id, [destination], target)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        document.status = "failed"
        job.status = "failed"
        job.error = error
        db.commit()
        return IngestFileResult(file=name, chunks=0, error=error)

    document.status = "indexed"
    job.status = "completed"
    job.total_chunks = total_chunks
    db.commit()
    return IngestFileResult(file=name, chunks=total_chunks)


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

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(data)
        temp_path = Path(tmp.name)

    try:
        return ingest_path_document(
            db=db,
            workspace_id=workspace_id,
            identity_id=identity_id,
            target=target,
            source_path=temp_path,
            filename=filename,
            content_type=content_type,
            storage_dir=storage_dir,
            ingest_func=ingest_func,
        )
    finally:
        temp_path.unlink(missing_ok=True)


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
