"""Small, restart-aware in-process executor for local document ingestion."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, update
from sqlalchemy.orm import aliased

from chatmaster.config import get_settings
from chatmaster.db.models import Document, IngestJob
from chatmaster.db.session import SessionLocal
from chatmaster.documents.service import document_operation_lock
from chatmaster.services.ingest_service import ingest

logger = logging.getLogger(__name__)
_LOCK = threading.Lock()
_EXECUTOR: ThreadPoolExecutor | None = None


def _executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    with _LOCK:
        if _EXECUTOR is None:
            _EXECUTOR = ThreadPoolExecutor(
                max_workers=max(1, get_settings().ingest_workers),
                thread_name_prefix="chatmaster-ingest",
            )
        return _EXECUTOR


def _claim_job(db, *, job_id: str, document_id: str) -> bool:
    """Atomically claim a pending job when no sibling job is already running."""
    other_job = aliased(IngestJob)
    claimed = db.execute(
        update(IngestJob)
        .where(
            IngestJob.id == job_id,
            IngestJob.status == "pending",
            ~select(other_job.id)
            .where(
                other_job.document_id == document_id,
                other_job.status == "running",
                other_job.id != job_id,
            )
            .exists(),
        )
        .values(status="running", error=None)
    ).rowcount
    return claimed == 1


def _run_job(job_id: str) -> None:
    with SessionLocal() as db:
        initial_job = db.get(IngestJob, job_id)
        if initial_job is None:
            return
        document_id = initial_job.document_id
        with document_operation_lock(initial_job.document_id):
            if not _claim_job(db, job_id=job_id, document_id=document_id):
                db.rollback()
                return
            db.commit()
            job = db.get(IngestJob, job_id)
            if job is None:
                return
            document = db.get(Document, job.document_id)
            if document is None:
                job.status = "failed"
                job.error = "Document not found"
                db.commit()
                return
            document.status = "ingesting"
            db.commit()
            try:
                result = ingest(
                    document.identity_id,
                    [__import__("pathlib").Path(document.storage_path)],
                    target=document.namespace,
                    workspace_id=document.workspace_id,
                    db=db,
                )
                db.expire_all()
                document = db.get(Document, job.document_id)
                job = db.get(IngestJob, job_id)
                if document is None or job is None or job.status != "running":
                    raise RuntimeError("Document was removed while it was being indexed")
                errors = [item.error for item in result.files if item.error]
                if errors or result.total_chunks == 0:
                    raise RuntimeError("; ".join(errors) or "No indexable content was produced")
                job.status = "completed"
                job.total_chunks = result.total_chunks
                job.error = None
                document.status = "indexed"
            except Exception as exc:
                logger.exception("Ingest job failed job_id=%s document_id=%s", job_id, document_id)
                db.rollback()
                job = db.get(IngestJob, job_id)
                document = db.get(Document, job.document_id) if job is not None else None
                if job is not None:
                    job.status = "failed"
                    job.error = f"{type(exc).__name__}: {exc}"
                if document is not None:
                    document.status = "failed"
            db.commit()


def enqueue_job(job_id: str) -> None:
    _executor().submit(_run_job, job_id)


def resume_pending_jobs() -> int:
    with SessionLocal() as db:
        running = list(db.scalars(select(IngestJob).where(IngestJob.status == "running")))
        for job in running:
            job.status = "pending"
            job.error = "Interrupted by process restart; resumed automatically."
        db.commit()
        pending_ids = list(db.scalars(select(IngestJob.id).where(IngestJob.status == "pending")))
    for job_id in pending_ids:
        enqueue_job(job_id)
    return len(pending_ids)


def shutdown_jobs() -> None:
    global _EXECUTOR
    with _LOCK:
        executor = _EXECUTOR
        _EXECUTOR = None
    if executor is not None:
        executor.shutdown(wait=True, cancel_futures=False)


def enqueue_index_rebuild(*, workspace_id: str, identity_id: str | None, target: str) -> None:
    def run() -> None:
        from chatmaster.retrieval.indexes import rebuild_index

        with SessionLocal() as db:
            try:
                rebuild_index(
                    db,
                    workspace_id=workspace_id,
                    identity_id=identity_id,
                    target=target,
                )
            except Exception:
                logger.exception(
                    "Index rebuild failed workspace_id=%s identity_id=%s target=%s",
                    workspace_id,
                    identity_id,
                    target,
                )

    _executor().submit(run)
