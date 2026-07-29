"""Local database initialization for the demo runtime."""

from __future__ import annotations

from chatmaster.db.base import Base
from chatmaster.db.session import engine


def init_db() -> None:
    from chatmaster.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def migrate_db() -> None:
    """Upgrade the runtime database, adopting legacy create_all databases once."""
    import shutil
    from datetime import datetime
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from chatmaster.config import get_settings

    settings = get_settings()
    ini_path = Path(__file__).parents[2] / "alembic.ini"
    config = Config(str(ini_path))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if tables and "alembic_version" not in tables:
        if settings.database_url.startswith("sqlite:///"):
            db_path = Path(settings.database_url.removeprefix("sqlite:///"))
            if db_path.exists():
                suffix = datetime.now().strftime("%Y%m%d%H%M%S")
                shutil.copy2(db_path, db_path.with_suffix(db_path.suffix + f".{suffix}.bak"))
        message_columns = (
            {column["name"] for column in inspector.get_columns("messages")}
            if "messages" in tables
            else set()
        )
        identity_columns = (
            {column["name"] for column in inspector.get_columns("identities")}
            if "identities" in tables
            else set()
        )
        # A database created by the current model already contains the reliability
        # and persona fields; adopt it at head. Older create_all databases need
        # the corresponding incremental upgrades.
        if {"avatar_url", "is_system"}.issubset(identity_columns):
            adopt_revision = "0003_persona_management"
        elif {"request_id", "status"}.issubset(message_columns):
            adopt_revision = "0002_reliability_fields"
        else:
            adopt_revision = "0001_baseline"
        command.stamp(
            config,
            adopt_revision,
        )
    command.upgrade(config, "head")
