"""Preview or remove retired physical Qdrant collections."""

from __future__ import annotations

import typer

from chatmaster.config import get_settings
from chatmaster.db.init_db import init_db
from chatmaster.db.session import SessionLocal
from chatmaster.retrieval.indexes import cleanup_retired_indexes

app = typer.Typer(add_completion=False)


@app.command()
def main(confirm: bool = typer.Option(False, "--confirm")) -> None:
    """Preview cleanup by default; pass --confirm to delete collections."""
    settings = get_settings()
    init_db()
    with SessionLocal() as db:
        names = cleanup_retired_indexes(
            db, workspace_id=settings.local_workspace_id, confirm=confirm
        )
    if not names:
        typer.echo("No retired or failed index collections found.")
    elif confirm:
        typer.echo(f"Deleted {len(names)} collection(s): {', '.join(names)}")
    else:
        typer.echo(f"Would delete {len(names)} collection(s): {', '.join(names)}")
        typer.echo("Run again with --confirm to delete them.")


if __name__ == "__main__":
    app()
