from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from chatmaster.db.base import Base
from chatmaster.db.models import Document, IngestJob, Workspace


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def test_ingest_uploaded_document_creates_document_and_job(tmp_path: Path) -> None:
    from chatmaster.documents.service import ingest_uploaded_document

    def fake_ingest(_identity_id, _paths, _target):
        return 3

    with _session() as db:
        db.add(Workspace(id="local", name="Local Workspace"))
        db.commit()

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
        db.add(Workspace(id="local", name="Local Workspace"))
        db.commit()

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
