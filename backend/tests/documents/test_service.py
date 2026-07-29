from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from chatmaster.db.base import Base
from chatmaster.db.models import Document, Identity, IngestJob, Workspace


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def _seed_identity(db: Session) -> None:
    db.add(Workspace(id="local", name="Local Workspace"))
    db.add(
        Identity(
            id="legal_expert",
            workspace_id="local",
            slug="legal_expert",
            name="Legal",
            description="",
            system_prompt="",
            private_collection="chatmaster_legal_expert",
        )
    )
    db.commit()


def test_ingest_uploaded_document_creates_document_and_job(tmp_path: Path) -> None:
    from chatmaster.documents.service import ingest_uploaded_document

    def fake_ingest(_identity_id, _paths, _target):
        return 3

    with _session() as db:
        _seed_identity(db)

        result = ingest_uploaded_document(
            db=db,
            workspace_id="local",
            identity_id="legal_expert",
            target="private",
            filename="note.txt",
            content_type="text/plain",
            data=b"hello",
            storage_dir=tmp_path,
            ingest_func=fake_ingest,
        )

        document = db.query(Document).one()
        job = db.query(IngestJob).one()

    assert result.file == "note.txt"
    assert result.chunks == 3
    assert document.status == "indexed"
    assert Path(document.storage_path).exists()
    assert job.status == "completed"
    assert job.total_chunks == 3


def test_ingest_uploaded_document_marks_failed_job_on_ingest_error(tmp_path: Path) -> None:
    from chatmaster.documents.service import ingest_uploaded_document

    def failing_ingest(_identity_id, _paths, _target):
        raise RuntimeError("embedding failed")

    with _session() as db:
        _seed_identity(db)

        result = ingest_uploaded_document(
            db=db,
            workspace_id="local",
            identity_id="legal_expert",
            target="private",
            filename="note.txt",
            content_type="text/plain",
            data=b"hello",
            storage_dir=tmp_path,
            ingest_func=failing_ingest,
        )

        document = db.query(Document).one()
        job = db.query(IngestJob).one()

    assert result.error == "RuntimeError: embedding failed"
    assert document.status == "failed"
    assert job.status == "failed"
    assert job.error == "RuntimeError: embedding failed"


def test_default_ingest_marks_document_failed_when_inner_ingest_reports_an_error(
    tmp_path: Path, monkeypatch
) -> None:
    from chatmaster.documents import service
    from chatmaster.schemas.api import IngestFileResult, IngestResult

    def failed_ingest(_identity_id, _paths, *, target, workspace_id, db):
        return IngestResult(
            identity_id="legal_expert",
            target=target,
            collection="chatmaster_legal_expert",
            files=[IngestFileResult(file="note.txt", error="Qdrant unavailable")],
            total_chunks=0,
        )

    monkeypatch.setattr(service, "ingest", failed_ingest)
    with _session() as db:
        _seed_identity(db)

        result = service.ingest_uploaded_document(
            db=db,
            workspace_id="local",
            identity_id="legal_expert",
            target="private",
            filename="note.txt",
            content_type="text/plain",
            data=b"hello",
            storage_dir=tmp_path,
        )
        document = db.query(Document).one()
        job = db.query(IngestJob).one()

    assert result.error == "RuntimeError: note.txt: Qdrant unavailable"
    assert document.status == "failed"
    assert job.status == "failed"


def test_ingest_uploaded_document_rejects_unsupported_extension(tmp_path: Path) -> None:
    from chatmaster.documents.service import UnsupportedDocumentType, ingest_uploaded_document

    with _session() as db:
        db.add(Workspace(id="local", name="Local Workspace"))
        db.commit()

        with pytest.raises(UnsupportedDocumentType, match="Unsupported file type"):
            ingest_uploaded_document(
                db=db,
                workspace_id="local",
                identity_id="legal_expert",
                target="private",
                filename="note.exe",
                content_type="application/octet-stream",
                data=b"hello",
                storage_dir=tmp_path,
                ingest_func=lambda *_args: 0,
            )


@pytest.mark.asyncio
async def test_common_upload_submission_deduplicates_with_non_null_scope(tmp_path: Path) -> None:
    from chatmaster.documents.service import submit_upload

    class Upload:
        filename = "shared.txt"
        content_type = "text/plain"

        def __init__(self) -> None:
            self.sent = False

        async def read(self, _size: int) -> bytes:
            if self.sent:
                return b""
            self.sent = True
            return b"shared content"

    with _session() as db:
        db.add(Workspace(id="local", name="Local Workspace"))
        db.commit()
        first, _ = await submit_upload(
            db=db,
            workspace_id="local",
            identity_id=None,
            target="common",
            upload=Upload(),
            storage_dir=tmp_path,
            max_bytes=1024,
        )
        second, _ = await submit_upload(
            db=db,
            workspace_id="local",
            identity_id=None,
            target="common",
            upload=Upload(),
            storage_dir=tmp_path,
            max_bytes=1024,
        )
        documents = db.query(Document).all()

    assert len(documents) == 1
    assert documents[0].scope_key == "common"
    assert first.document_id == second.document_id
    assert second.duplicate is True
