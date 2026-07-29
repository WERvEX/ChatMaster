"""Document ingestion and listing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from chatmaster.config import get_settings
from chatmaster.core.auth import get_current_workspace_id
from chatmaster.db.models import Document, IngestJob
from chatmaster.db.session import get_db
from chatmaster.documents.service import (
    UnsupportedDocumentType,
    delete_document,
    list_documents,
    list_ingest_jobs,
    retry_ingest_job,
    submit_upload,
)
from chatmaster.identities.service import IdentityNotFound, get_identity_model
from chatmaster.schemas.api import (
    DocumentOut,
    IndexRebuildRequest,
    IndexVersionOut,
    IngestJobOut,
    IngestSubmission,
)

router = APIRouter(tags=["documents"])


@router.post(
    "/api/documents/ingest",
    response_model=IngestSubmission,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_documents(
    files: list[UploadFile] = File(...),
    identity_id: str | None = Form(None),
    target: str = Form("private"),
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    if target not in {"private", "common"}:
        raise HTTPException(status_code=400, detail="target must be 'private' or 'common'")

    if target == "private":
        if not identity_id:
            raise HTTPException(status_code=400, detail="identity_id is required")
        try:
            get_identity_model(db, workspace_id=workspace_id, identity_id=identity_id)
        except IdentityNotFound:
            raise HTTPException(
                status_code=404, detail=f"Identity '{identity_id}' not found"
            ) from None

    settings = get_settings()
    submissions = []
    batch_bytes = 0

    for uploaded in files:
        try:
            item, size = await submit_upload(
                db=db,
                workspace_id=workspace_id,
                identity_id=identity_id,
                target=target,
                upload=uploaded,
                storage_dir=settings.storage_dir,
                max_bytes=min(
                    settings.upload_max_bytes,
                    settings.upload_batch_max_bytes - batch_bytes,
                ),
            )
            batch_bytes += size
            submissions.append(item)
            if item.job_id and not item.duplicate:
                from chatmaster.documents.jobs import enqueue_job

                enqueue_job(item.job_id)
        except ValueError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except UnsupportedDocumentType as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except IdentityNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IngestSubmission(items=submissions)


@router.get("/api/documents", response_model=list[DocumentOut])
async def get_documents(
    identity_id: str | None = Query(None),
    namespace: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    return list_documents(
        db,
        workspace_id=workspace_id,
        identity_id=identity_id,
        namespace=namespace,
        status=status,
    )[offset : offset + limit]


@router.get("/api/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: str,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    document = db.get(Document, document_id)
    if document is None or document.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/api/ingest-jobs", response_model=list[IngestJobOut])
async def get_ingest_jobs(
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    return list_ingest_jobs(db, workspace_id=workspace_id, status=status)[offset : offset + limit]


@router.get("/api/ingest-jobs/{job_id}", response_model=IngestJobOut)
async def get_ingest_job(
    job_id: str,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    job = db.get(IngestJob, job_id)
    if job is None or job.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Ingest job not found")
    return job


@router.post(
    "/api/ingest-jobs/{job_id}/retry",
    response_model=IngestJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_job(
    job_id: str,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    try:
        job = retry_ingest_job(db, workspace_id=workspace_id, job_id=job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Ingest job not found") from None
    from chatmaster.documents.jobs import enqueue_job

    enqueue_job(job.id)
    return job


@router.delete("/api/documents/{document_id}", status_code=204)
async def remove_document(
    document_id: str,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    try:
        delete_document(db, workspace_id=workspace_id, document_id=document_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found") from None
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="Document cleanup failed") from exc


@router.get("/api/indexes", response_model=list[IndexVersionOut])
async def get_indexes(
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    from chatmaster.db.models import IndexVersion

    return list(
        db.scalars(
            select(IndexVersion)
            .where(IndexVersion.workspace_id == workspace_id)
            .order_by(IndexVersion.updated_at.desc())
        )
    )


@router.post("/api/indexes/rebuild", status_code=status.HTTP_202_ACCEPTED)
async def post_index_rebuild(
    body: IndexRebuildRequest,
    workspace_id: str = Depends(get_current_workspace_id),
):
    if body.target == "private" and not body.identity_id:
        raise HTTPException(status_code=400, detail="identity_id is required")
    from chatmaster.documents.jobs import enqueue_index_rebuild

    enqueue_index_rebuild(
        workspace_id=workspace_id,
        identity_id=body.identity_id,
        target=body.target,
    )
    return {"status": "accepted", "target": body.target, "identity_id": body.identity_id}
