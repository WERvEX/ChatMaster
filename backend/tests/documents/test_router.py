from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from chatmaster.db.base import Base
from chatmaster.db.models import Document, IngestJob, Workspace
from chatmaster.db.session import get_db
from chatmaster.routers.documents import router


def _client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with SessionLocal() as db:
        db.add(Workspace(id="local", name="Local Workspace"))
        db.add(
            Document(
                id="document-1",
                workspace_id="local",
                identity_id="legal_expert",
                namespace="private",
                filename="note.txt",
                content_type="text/plain",
                storage_path="data/storage/local/documents/document-1/note.txt",
                sha256="a" * 64,
                status="indexed",
            )
        )
        db.add(
            IngestJob(
                id="job-1",
                workspace_id="local",
                document_id="document-1",
                status="completed",
                total_chunks=2,
            )
        )
        db.commit()

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        with SessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_list_documents_endpoint_returns_persisted_documents() -> None:
    client = _client()

    response = client.get("/api/documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == "document-1"
    assert payload[0]["filename"] == "note.txt"


def test_list_ingest_jobs_endpoint_returns_persisted_jobs() -> None:
    client = _client()

    response = client.get("/api/ingest-jobs")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == "job-1"
    assert payload[0]["status"] == "completed"
