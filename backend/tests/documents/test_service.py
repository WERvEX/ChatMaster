from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from chatmaster.db.base import Base
from chatmaster.db.models import (
    Document,
    DocumentChunk,
    Identity,
    IndexVersion,
    IngestJob,
    Workspace,
)


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


def test_retry_only_allows_failed_jobs() -> None:
    from chatmaster.documents.service import DocumentOperationConflict, retry_ingest_job

    with _session() as db:
        _seed_identity(db)
        document = Document(
            id="document-1",
            workspace_id="local",
            identity_id="legal_expert",
            namespace="private",
            scope_key="legal_expert",
            filename="note.txt",
            storage_path="note.txt",
            sha256="b" * 64,
            status="pending",
        )
        db.add_all(
            [
                document,
                IngestJob(
                    id="job-1",
                    workspace_id="local",
                    document_id=document.id,
                    status="pending",
                    total_chunks=0,
                ),
            ]
        )
        db.commit()

        with pytest.raises(DocumentOperationConflict, match="Only failed"):
            retry_ingest_job(db, workspace_id="local", job_id="job-1")


def test_worker_claim_allows_only_one_running_job_per_document() -> None:
    from chatmaster.documents.jobs import _claim_job

    with _session() as db:
        _seed_identity(db)
        document = Document(
            id="document-1",
            workspace_id="local",
            identity_id="legal_expert",
            namespace="private",
            scope_key="legal_expert",
            filename="note.txt",
            storage_path="note.txt",
            sha256="d" * 64,
            status="pending",
        )
        db.add_all(
            [
                document,
                IngestJob(
                    id="job-1",
                    workspace_id="local",
                    document_id=document.id,
                    status="pending",
                    total_chunks=0,
                ),
                IngestJob(
                    id="job-2",
                    workspace_id="local",
                    document_id=document.id,
                    status="pending",
                    total_chunks=0,
                ),
            ]
        )
        db.commit()

        assert _claim_job(db, job_id="job-1", document_id=document.id)
        db.commit()
        assert not _claim_job(db, job_id="job-2", document_id=document.id)


def test_delete_document_cleans_vectors_and_persisted_records(tmp_path: Path, monkeypatch) -> None:
    from chatmaster.documents.service import delete_document

    stored_path = tmp_path / "note.txt"
    stored_path.write_text("hello", encoding="utf-8")
    deleted: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        "chatmaster.ai.vectorstore.delete_points",
        lambda collection, ids: deleted.append((collection, ids)),
    )

    with _session() as db:
        _seed_identity(db)
        document = Document(
            id="document-1",
            workspace_id="local",
            identity_id="legal_expert",
            namespace="private",
            scope_key="legal_expert",
            filename="note.txt",
            storage_path=str(stored_path),
            sha256="c" * 64,
            status="indexed",
        )
        version = IndexVersion(
            id="version-1",
            workspace_id="local",
            namespace="private",
            identity_id="legal_expert",
            collection_name="private-v1",
            embedding_provider="test",
            embedding_model="test",
            embedding_dim=3,
            status="active",
        )
        db.add_all(
            [
                document,
                version,
                DocumentChunk(
                    id="chunk-1",
                    workspace_id="local",
                    document_id=document.id,
                    index_version_id=version.id,
                    qdrant_point_id="point-1",
                    chunk_index=0,
                    text="hello",
                    metadata_json={},
                ),
                IngestJob(
                    id="job-1",
                    workspace_id="local",
                    document_id=document.id,
                    status="completed",
                    total_chunks=1,
                ),
            ]
        )
        db.commit()

        delete_document(db, workspace_id="local", document_id=document.id)

        assert db.get(Document, document.id) is None
        assert db.query(DocumentChunk).count() == 0
        assert db.query(IngestJob).count() == 0

    assert deleted == [("private-v1", ["point-1"])]
    assert not stored_path.exists()
