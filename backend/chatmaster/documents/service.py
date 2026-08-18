"""Document persistence plus synchronous ingestion for the local MVP."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import threading
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from chatmaster.ai.loaders import SUPPORTED_EXTENSIONS
from chatmaster.db.models import Document, DocumentChunk, IndexVersion, IngestJob
from chatmaster.identities.service import get_identity_model
from chatmaster.schemas.api import IngestFileResult, IngestSubmissionItem
from chatmaster.services.ingest_service import ingest


class UnsupportedDocumentType(ValueError):
    pass


class DocumentOperationConflict(RuntimeError):
    """Raised when a document already has an active operation."""


_DOCUMENT_LOCKS_GUARD = threading.Lock()
_DOCUMENT_LOCKS: dict[str, threading.RLock] = {}


@contextmanager
def document_operation_lock(document_id: str):
    with _DOCUMENT_LOCKS_GUARD:
        lock = _DOCUMENT_LOCKS.setdefault(document_id, threading.RLock())
    with lock:
        yield


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _default_ingest(
    identity_id: str | None,
    paths: list[Path],
    target: str,
    *,
    workspace_id: str,
    db: Session,
) -> int:
    result = ingest(identity_id, paths, target=target, workspace_id=workspace_id, db=db)
    failures = [f"{item.file}: {item.error}" for item in result.files if item.error]
    if failures:
        raise RuntimeError("; ".join(failures))
    if result.total_chunks == 0:
        raise ValueError("No indexable content was produced")
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
    identity_id: str | None,
    target: str,
    source_path: Path,
    filename: str | None = None,
    content_type: str | None = None,
    storage_dir: str | Path,
    ingest_func: Callable[[str | None, list[Path], str], int] | None = None,
) -> IngestFileResult:
    if target == "private":
        if not identity_id:
            raise ValueError("identity_id is required for private ingestion")
        get_identity_model(db, workspace_id=workspace_id, identity_id=identity_id)

    path = Path(source_path)
    name = filename or path.name
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentType(f"Unsupported file type: {name}")

    namespace = _document_namespace(target)
    identity_for_document = None if namespace == "common" else identity_id
    scope_key = "common" if namespace == "common" else str(identity_id)
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
            scope_key=scope_key,
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
        if ingest_func is None:
            total_chunks = _default_ingest(
                identity_id, [destination], target, workspace_id=workspace_id, db=db
            )
        else:
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
    identity_id: str | None,
    target: str,
    filename: str,
    content_type: str | None,
    data: bytes,
    storage_dir: str | Path,
    ingest_func: Callable[[str | None, list[Path], str], int] | None = None,
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


async def submit_upload(
    *,
    db: Session,
    workspace_id: str,
    identity_id: str | None,
    target: str,
    upload,
    storage_dir: str | Path,
    max_bytes: int,
) -> tuple[IngestSubmissionItem, int]:
    """Stream one upload to durable storage and create a pending ingestion job."""
    if target == "private":
        if not identity_id:
            raise ValueError("identity_id is required for private ingestion")
        get_identity_model(db, workspace_id=workspace_id, identity_id=identity_id)
    filename = Path(upload.filename or "uploaded").name
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentType(f"Unsupported file type: {filename}")

    storage_root = Path(storage_dir)
    upload_root = storage_root / ".uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    temp_path = upload_root / f"{uuid.uuid4().hex}{ext}.part"
    digest = hashlib.sha256()
    total = 0
    try:
        with temp_path.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"{filename} exceeds upload size limit")
                digest.update(chunk)
                output.write(chunk)

        namespace = _document_namespace(target)
        scope_key = "common" if namespace == "common" else str(identity_id)
        existing = db.scalars(
            select(Document).where(
                Document.workspace_id == workspace_id,
                Document.sha256 == digest.hexdigest(),
                Document.scope_key == scope_key,
            )
        ).first()
        if existing is not None:
            latest = db.scalars(
                select(IngestJob)
                .where(IngestJob.document_id == existing.id)
                .order_by(IngestJob.created_at.desc())
            ).first()
            return (
                IngestSubmissionItem(
                    file=filename,
                    document_id=existing.id,
                    job_id=latest.id if latest else None,
                    status=existing.status,
                    duplicate=True,
                ),
                total,
            )

        document_id = str(uuid.uuid4())
        destination_dir = storage_root / workspace_id / "documents" / document_id
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / filename
        temp_path.replace(destination)
        document = Document(
            id=document_id,
            workspace_id=workspace_id,
            identity_id=None if namespace == "common" else identity_id,
            namespace=namespace,
            scope_key=scope_key,
            filename=filename,
            content_type=upload.content_type,
            storage_path=str(destination),
            sha256=digest.hexdigest(),
            status="pending",
        )
        job = IngestJob(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            document_id=document_id,
            status="pending",
            error=None,
            total_chunks=0,
        )
        db.add_all([document, job])
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            destination.unlink(missing_ok=True)
            existing = db.scalars(
                select(Document).where(
                    Document.workspace_id == workspace_id,
                    Document.sha256 == digest.hexdigest(),
                    Document.scope_key == scope_key,
                )
            ).one()
            latest = db.scalars(
                select(IngestJob)
                .where(IngestJob.document_id == existing.id)
                .order_by(IngestJob.created_at.desc())
            ).first()
            return (
                IngestSubmissionItem(
                    file=filename,
                    document_id=existing.id,
                    job_id=latest.id if latest else None,
                    status=existing.status,
                    duplicate=True,
                ),
                total,
            )
        return (
            IngestSubmissionItem(
                file=filename,
                document_id=document.id,
                job_id=job.id,
                status=job.status,
            ),
            total,
        )
    finally:
        temp_path.unlink(missing_ok=True)


def retry_ingest_job(db: Session, *, workspace_id: str, job_id: str) -> IngestJob:
    old = db.get(IngestJob, job_id)
    if old is None or old.workspace_id != workspace_id:
        raise KeyError(job_id)
    document = db.get(Document, old.document_id)
    if document is None:
        raise KeyError(old.document_id)
    with document_operation_lock(document.id):
        db.refresh(old)
        if old.status != "failed":
            raise DocumentOperationConflict("Only failed ingest jobs can be retried")
        active = db.scalars(
            select(IngestJob).where(
                IngestJob.document_id == document.id,
                IngestJob.status.in_(("pending", "running")),
            )
        ).first()
        if active is not None:
            raise DocumentOperationConflict("Document already has an active ingest job")
        job = IngestJob(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            document_id=document.id,
            status="pending",
            error=None,
            total_chunks=0,
        )
        document.status = "pending"
        db.add(job)
        db.commit()
        db.refresh(job)
        return job


def delete_document(db: Session, *, workspace_id: str, document_id: str) -> None:
    document = db.get(Document, document_id)
    if document is None or document.workspace_id != workspace_id:
        raise KeyError(document_id)
    with document_operation_lock(document_id):
        db.refresh(document)
        active = db.scalars(
            select(IngestJob).where(
                IngestJob.document_id == document_id,
                IngestJob.status.in_(("pending", "running")),
            )
        ).first()
        if active is not None:
            raise DocumentOperationConflict("Document is still being indexed")
        try:
            from chatmaster.ai.vectorstore import delete_points

            chunks = list(
                db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document_id))
            )
            by_collection: dict[str, list[str]] = {}
            for chunk in chunks:
                version = db.get(IndexVersion, chunk.index_version_id)
                if version is not None:
                    by_collection.setdefault(version.collection_name, []).append(
                        chunk.qdrant_point_id
                    )
            for collection, point_ids in by_collection.items():
                delete_points(collection, point_ids)
            stored_path = Path(document.storage_path)
            stored_path.unlink(missing_ok=True)
            db.delete(document)
            db.commit()
        except Exception:
            db.rollback()
            document = db.get(Document, document_id)
            if document is not None:
                document.status = "delete_failed"
                db.commit()
            raise
