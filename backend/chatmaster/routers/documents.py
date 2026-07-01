"""Document ingestion and listing endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from chatmaster.config import get_settings
from chatmaster.core.auth import get_current_workspace_id
from chatmaster.db.models import Document, IngestJob
from chatmaster.db.session import get_db
from chatmaster.documents.service import (
    UnsupportedDocumentType,
    ingest_uploaded_document,
    list_documents,
    list_ingest_jobs,
)
from chatmaster.identities.loader import IdentityNotFound, get_registry
from chatmaster.schemas.api import DocumentOut, IngestJobOut, IngestResult

router = APIRouter(tags=["documents"])


@router.post("/api/documents/ingest", response_model=IngestResult)
async def ingest_documents(
    files: list[UploadFile] = File(...),
    identity_id: str = Form(...),
    target: str = Form("private"),
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    if target not in {"private", "common"}:
        raise HTTPException(status_code=400, detail="target must be 'private' or 'common'")

    try:
        get_registry().get(identity_id)
    except IdentityNotFound:
        raise HTTPException(status_code=404, detail=f"Identity '{identity_id}' not found") from None

    settings = get_settings()
    file_results = []

    for uploaded in files:
        filename = Path(uploaded.filename or "uploaded").name
        data = await uploaded.read()
        if len(data) > settings.upload_max_bytes:
            raise HTTPException(status_code=413, detail=f"{filename} exceeds upload size limit")
        try:
            result = ingest_uploaded_document(
                db=db,
                workspace_id=workspace_id,
                identity_id=identity_id,
                target=target,
                filename=filename,
                content_type=uploaded.content_type,
                data=data,
                storage_dir=settings.storage_dir,
            )
        except UnsupportedDocumentType as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except IdentityNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        file_results.append(result)

    return IngestResult(
        identity_id=identity_id,
        target=target,
        collection=(
            settings.common_collection
            if target == "common"
            else get_registry().get(identity_id).private_collection
        ),
        files=file_results,
        total_chunks=sum(file.chunks for file in file_results),
    )


@router.get("/api/documents", response_model=list[DocumentOut])
async def get_documents(
    identity_id: str | None = Query(None),
    namespace: str | None = Query(None),
    status: str | None = Query(None),
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    return list_documents(
        db,
        workspace_id=workspace_id,
        identity_id=identity_id,
        namespace=namespace,
        status=status,
    )


@router.get("/api/documents/{document_id}", response_model=DocumentOut)
async def get_document(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/api/ingest-jobs", response_model=list[IngestJobOut])
async def get_ingest_jobs(
    status: str | None = Query(None),
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    return list_ingest_jobs(db, workspace_id=workspace_id, status=status)


@router.get("/api/ingest-jobs/{job_id}", response_model=IngestJobOut)
async def get_ingest_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(IngestJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingest job not found")
    return job
