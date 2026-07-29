from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from chatmaster.db.base import Base
from chatmaster.db.models import Identity, Workspace
from chatmaster.db.session import get_db
from chatmaster.routers.identities import router


def _client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    with SessionLocal() as db:
        db.add(Workspace(id="local", name="Local"))
        db.add(
            Identity(
                id="general_assistant",
                workspace_id="local",
                slug="general_assistant",
                name="通用助手",
                description="",
                system_prompt="通用回答",
                private_collection="general",
                is_system=True,
            )
        )
        db.commit()
    app = FastAPI()
    app.include_router(router)

    def override():
        with SessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override
    return TestClient(app)


def test_identity_create_update_archive_restore_flow() -> None:
    client = _client()
    payload = {
        "name": "产品顾问",
        "description": "产品策略",
        "system_prompt": "你是一位产品顾问。",
        "avatar_url": None,
        "generation_model": None,
        "embedding_model": None,
        "retrieval": {
            "top_k": 6,
            "private_weight": 0.6,
            "common_weight": 0.4,
            "min_chunks_common": 2,
        },
    }
    created = client.post("/api/identities", json=payload)
    assert created.status_code == 200
    identity_id = created.json()["id"]

    payload["name"] = "高级产品顾问"
    updated = client.put(f"/api/identities/{identity_id}", json=payload)
    assert updated.status_code == 200
    assert updated.json()["name"] == "高级产品顾问"

    archived = client.post(f"/api/identities/{identity_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["is_archived"] is True

    active_list = client.get("/api/identities").json()
    assert {item["id"] for item in active_list} == {"general_assistant"}

    restored = client.post(f"/api/identities/{identity_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["is_archived"] is False


def test_system_identity_cannot_be_archived() -> None:
    client = _client()
    response = client.post("/api/identities/general_assistant/archive")
    assert response.status_code == 409
