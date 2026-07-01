from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from chatmaster.db.base import Base
from chatmaster.db.models import Conversation, Identity, Message, Workspace
from chatmaster.db.session import get_db
from chatmaster.routers.conversations import router


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
            Identity(
                id="legal_expert",
                workspace_id="local",
                slug="legal_expert",
                name="法律专家",
                description="",
                system_prompt="",
                private_collection="chatmaster_legal_expert",
            )
        )
        db.commit()

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        with SessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), SessionLocal


def test_conversation_crud_flow() -> None:
    client, SessionLocal = _client()

    create_resp = client.post(
        "/api/conversations",
        json={"identity_id": "legal_expert", "title": "测试会话"},
    )
    assert create_resp.status_code == 200
    conversation_id = create_resp.json()["id"]
    assert create_resp.json()["title"] == "测试会话"

    list_resp = client.get("/api/conversations", params={"identity_id": "legal_expert"})
    assert list_resp.status_code == 200
    assert list_resp.json()[0]["id"] == conversation_id

    with SessionLocal() as db:
        db.add(
            Message(
                id="message-1",
                workspace_id="local",
                conversation_id=conversation_id,
                role="user",
                content="你好",
            )
        )
        db.commit()

    messages_resp = client.get(f"/api/conversations/{conversation_id}/messages")
    assert messages_resp.status_code == 200
    assert messages_resp.json()[0]["content"] == "你好"

    delete_resp = client.delete(f"/api/conversations/{conversation_id}")
    assert delete_resp.status_code == 204

    with SessionLocal() as db:
        assert db.get(Conversation, conversation_id) is None
        assert db.query(Message).count() == 0


def test_create_conversation_unknown_identity_returns_404() -> None:
    client, _ = _client()

    response = client.post(
        "/api/conversations",
        json={"identity_id": "missing", "title": "x"},
    )

    assert response.status_code == 404
