from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chatmaster.db.base import Base
from chatmaster.db.models import Document, Identity, IndexVersion, Workspace


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)


class _Settings:
    local_workspace_id = "local"
    common_collection = "common"


def test_active_collection_uses_active_version(monkeypatch) -> None:
    from chatmaster.retrieval import indexes

    SessionLocal = _session()
    with SessionLocal() as db:
        db.add(Workspace(id="local", name="Local"))
        db.add(
            Identity(
                id="legal_expert",
                workspace_id="local",
                slug="legal_expert",
                name="Legal",
                description="",
                system_prompt="",
                private_collection="legal",
            )
        )
        db.add(
            IndexVersion(
                id="version-1",
                workspace_id="local",
                namespace="private",
                identity_id="legal_expert",
                collection_name="legal__v_new",
                embedding_provider="test",
                embedding_model="test",
                embedding_dim=3,
                status="active",
            )
        )
        db.commit()
    with SessionLocal() as db:
        assert (
            indexes.active_collection(
                db,
                workspace_id="local",
                logical_name="legal",
                identity_id="legal_expert",
            )
            == "legal__v_new"
        )


def test_rebuild_activates_new_version_only_after_success(tmp_path: Path, monkeypatch) -> None:
    from chatmaster.retrieval import indexes

    SessionLocal = _session()
    with SessionLocal() as db:
        db.add(Workspace(id="local", name="Local"))
        db.add(
            Identity(
                id="legal_expert",
                workspace_id="local",
                slug="legal_expert",
                name="Legal",
                description="",
                system_prompt="",
                private_collection="legal",
            )
        )
        db.add(
            Document(
                id="doc-1",
                workspace_id="local",
                identity_id="legal_expert",
                namespace="private",
                filename="note.txt",
                storage_path=str(tmp_path / "note.txt"),
                sha256="a" * 64,
                status="indexed",
            )
        )
        db.add(
            IndexVersion(
                id="old",
                workspace_id="local",
                namespace="private",
                identity_id="legal_expert",
                collection_name="legal",
                embedding_provider="old",
                embedding_model="old",
                embedding_dim=3,
                status="active",
            )
        )
        db.commit()

        monkeypatch.setattr(indexes, "get_settings", lambda: _Settings())
        monkeypatch.setattr(indexes, "ensure_collection", lambda *_: None)
        monkeypatch.setattr(
            indexes,
            "build_embeddings",
            lambda _: type(
                "E", (), {"model_name": "new", "embed_query": lambda *_: [0.0, 0.0, 0.0]}
            )(),
        )
        from chatmaster.services import ingest_service

        monkeypatch.setattr(
            ingest_service, "ingest", lambda *_args, **_kwargs: type("R", (), {"files": []})()
        )
        version = indexes.rebuild_index(
            db, workspace_id="local", identity_id="legal_expert", target="private"
        )
        assert version.status == "active"
        assert db.get(IndexVersion, "old").status == "retired"


def test_common_rebuild_uses_default_embeddings(tmp_path: Path, monkeypatch) -> None:
    from chatmaster.retrieval import indexes

    SessionLocal = _session()
    with SessionLocal() as db:
        db.add(Workspace(id="local", name="Local"))
        db.commit()
        monkeypatch.setattr(indexes, "get_settings", lambda: _Settings())
        monkeypatch.setattr(indexes, "ensure_collection", lambda *_: None)
        received = []

        def embeddings(identity):
            received.append(identity)
            return type("E", (), {"model_name": "default", "embed_query": lambda *_: [0.0]})()

        monkeypatch.setattr(indexes, "build_embeddings", embeddings)
        version = indexes.rebuild_index(db, workspace_id="local", identity_id=None, target="common")
        assert version.status == "active"

    assert received == [None]
