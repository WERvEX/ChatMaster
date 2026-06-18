"""Document ingestion endpoint: POST /api/documents/ingest (multipart upload)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from chatmaster.ai.loaders import SUPPORTED_EXTENSIONS
from chatmaster.config import get_settings
from chatmaster.services.ingest_service import ingest

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/ingest")
async def ingest_documents(
    files: list[UploadFile] = File(...),
    identity_id: str = Form(...),
    target: str = Form("private"),
):
    if target not in {"private", "common"}:
        raise HTTPException(status_code=400, detail="target must be 'private' or 'common'")

    settings = get_settings()
    saved_paths: list[Path] = []

    # Persist uploads to a temp dir, then ingest. ingest_service works on Paths.
    with tempfile.TemporaryDirectory() as tmp:
        for f in files:
            ext = Path(f.filename or "").suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                raise HTTPException(
                    status_code=400, detail=f"Unsupported file type: {f.filename}"
                )
            data = await f.read()
            if len(data) > settings.upload_max_bytes:
                raise HTTPException(
                    status_code=413, detail=f"{f.filename} exceeds upload size limit"
                )
            dest = Path(tmp) / (f.filename or "uploaded")
            dest.write_bytes(data)
            saved_paths.append(dest)

        result = ingest(identity_id, saved_paths, target=target)
        return result
