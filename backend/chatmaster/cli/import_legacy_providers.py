"""One-time import of the deprecated plaintext providers.json file."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from chatmaster.ai.providers import ProvidersConfig, save_provider_config
from chatmaster.config import get_settings
from chatmaster.db.init_db import init_db
from chatmaster.db.seed import seed_local_data
from chatmaster.db.session import SessionLocal

app = typer.Typer(add_completion=False)


@app.command()
def main(
    path: Path = typer.Option(..., "--path", exists=True, dir_okay=False),
    confirm: bool = typer.Option(False, "--confirm"),
) -> None:
    """Encrypt and import a legacy file; the plaintext source is never deleted."""
    if not confirm:
        raise typer.BadParameter("Pass --confirm to import credentials from a plaintext file.")
    payload = ProvidersConfig.model_validate(json.loads(path.read_text(encoding="utf-8")))
    settings = get_settings()
    init_db()
    with SessionLocal() as db:
        seed_local_data(db, settings)
    save_provider_config(payload, settings.local_workspace_id)
    typer.echo("Imported encrypted provider configuration. Remove the plaintext file manually.")


if __name__ == "__main__":
    app()
