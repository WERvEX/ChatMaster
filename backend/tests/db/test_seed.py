from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from chatmaster.db.base import Base
from chatmaster.db.models import Identity, User, Workspace


class DummySettings:
    local_workspace_id = "local"
    local_user_id = "local-user"
    default_generation_model = "deepseek-v4-pro"
    default_embedding_model = "BAAI/bge-small-zh-v1.5"


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def test_seed_local_data_inserts_workspace_user_yaml_identities_and_fallback(
    tmp_path: Path,
) -> None:
    from chatmaster.db.seed import seed_local_data

    identities_yaml = tmp_path / "identities.yaml"
    identities_yaml.write_text(
        """
identities:
  - id: legal_expert
    name: 法律专家
    description: 法律咨询
    system_prompt: |
      请基于资料回答。
    private_collection: chatmaster_legal_expert
    generation_model: deepseek-v4-pro
    retrieval:
      top_k: 6
      private_weight: 0.7
      common_weight: 0.3
""",
        encoding="utf-8",
    )

    with _session() as db:
        seed_local_data(db, DummySettings(), identities_yaml)
        seed_local_data(db, DummySettings(), identities_yaml)

        assert db.get(Workspace, "local") is not None
        assert db.get(User, "local-user") is not None

        identities = db.query(Identity).all()
        assert len(identities) == 2
        legal = next(item for item in identities if item.id == "legal_expert")
        fallback = next(item for item in identities if item.id == "general_assistant")
        assert legal.slug == "legal_expert"
        assert legal.retrieval_config_json["top_k"] == 6
        assert fallback.is_system is True
        assert fallback.is_active is True
