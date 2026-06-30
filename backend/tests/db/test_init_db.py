from __future__ import annotations

from sqlalchemy import create_engine, inspect

from chatmaster.db.base import Base


def test_init_db_creates_business_tables(monkeypatch) -> None:
    from chatmaster.db import init_db

    engine = create_engine("sqlite:///:memory:", future=True)
    monkeypatch.setattr(init_db, "engine", engine)

    init_db.init_db()

    tables = set(inspect(engine).get_table_names())
    assert {"workspaces", "identities", "provider_configs", "messages"}.issubset(tables)

    Base.metadata.drop_all(bind=engine)
