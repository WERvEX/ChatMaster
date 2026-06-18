"""CLI for bulk document ingestion.

Usage:
    python -m chatmaster.cli.ingest --identity legal_expert --path ./data/sample_docs/legal_expert
    python -m chatmaster.cli.ingest --identity legal_expert --path ./docs/common --common
    python -m chatmaster.cli.ingest --identity legal_expert --files a.pdf b.txt
"""

from __future__ import annotations

import os
from pathlib import Path

# HuggingFace mirror must be set before huggingface_hub is imported (see main.py).
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import typer

from chatmaster.ai.loaders import SUPPORTED_EXTENSIONS
from chatmaster.services.ingest_service import ingest

app = typer.Typer(add_completion=False, help="ChatMaster document ingestion CLI.")


def _collect_files(path: Path) -> list[Path]:
    files: list[Path] = []
    if path.is_file():
        files.append(path)
    else:
        for p in sorted(path.rglob("*")):
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(p)
    return files


@app.command()
def main(
    identity: str = typer.Option(..., "--identity", "-i", help="Identity id, e.g. legal_expert"),
    path: Path | None = typer.Option(None, "--path", "-p", help="Folder or file to ingest"),
    files: list[Path] | None = typer.Option(None, "--files", "-f", help="Explicit file(s)"),
    common: bool = typer.Option(False, "--common", help="Ingest into the shared common collection"),
):
    target = "common" if common else "private"

    candidates: list[Path] = []
    if path:
        candidates.extend(_collect_files(path))
    if files:
        candidates.extend(files)

    if not candidates:
        typer.echo("No files to ingest.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Ingesting {len(candidates)} file(s) into '{target}' for identity '{identity}'...")
    result = ingest(identity, candidates, target=target)

    for fr in result.files:
        if fr.error:
            typer.echo(f"  ✗ {fr.file}: {fr.error}")
        else:
            typer.echo(f"  ✓ {fr.file}: {fr.chunks} chunks")
    typer.echo(
        f"Done. Collection: {result.collection} | Total chunks: {result.total_chunks}"
    )


if __name__ == "__main__":
    app()
