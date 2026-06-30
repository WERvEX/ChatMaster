"""Local database initialization for the demo runtime."""

from __future__ import annotations

from chatmaster.db.base import Base
from chatmaster.db.session import engine


def init_db() -> None:
    from chatmaster.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
