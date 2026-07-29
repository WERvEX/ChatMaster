"""Explicit CLI entry point for non-destructive vector index rebuilds."""

from __future__ import annotations

import typer

from chatmaster.config import get_settings
from chatmaster.db.init_db import init_db
from chatmaster.db.seed import seed_local_data
from chatmaster.db.session import SessionLocal
from chatmaster.retrieval.indexes import rebuild_index

app = typer.Typer(add_completion=False)


@app.command()
def main(
    identity: str | None = typer.Option(None, "--identity", "-i"),
    common: bool = typer.Option(False, "--common"),
    confirm: bool = typer.Option(False, "--confirm", help="Actually start the rebuild"),
) -> None:
    """Create and activate a new index version without deleting the old one."""
    if not confirm:
        raise typer.BadParameter("Pass --confirm to start a potentially costly re-embedding job.")
    if not common and not identity:
        raise typer.BadParameter("--identity is required unless --common is used.")
    settings = get_settings()
    init_db()
    with SessionLocal() as db:
        seed_local_data(db, settings)
        version = rebuild_index(
            db,
            workspace_id=settings.local_workspace_id,
            identity_id=identity,
            target="common" if common else "private",
        )
    typer.echo(f"Active index: {version.collection_name}")


if __name__ == "__main__":
    app()
