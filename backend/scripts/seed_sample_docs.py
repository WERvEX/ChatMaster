"""Import all bundled sample documents into SQLite + Qdrant.

Run from the backend/ directory inside the chatmaster conda environment:

    conda activate chatmaster
    cd backend
    python scripts/seed_sample_docs.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = BACKEND_ROOT / "data" / "sample_docs"

IDENTITIES = ("legal_expert", "emotional_advisor", "prompt_engineer")


def main() -> int:
    if not SAMPLE_ROOT.exists():
        print(f"Sample docs folder not found: {SAMPLE_ROOT}", file=sys.stderr)
        return 1

    commands: list[list[str]] = []
    for identity in IDENTITIES:
        private_dir = SAMPLE_ROOT / identity
        if private_dir.exists() and any(private_dir.iterdir()):
            commands.append(
                [
                    sys.executable,
                    "-m",
                    "chatmaster.cli.ingest",
                    "-i",
                    identity,
                    "-p",
                    str(private_dir),
                ]
            )

    common_dir = SAMPLE_ROOT / "common"
    if common_dir.exists() and any(common_dir.iterdir()):
        commands.append(
            [
                sys.executable,
                "-m",
                "chatmaster.cli.ingest",
                "-i",
                "legal_expert",
                "-p",
                str(common_dir),
                "--common",
            ]
        )

    if not commands:
        print("No sample documents found to import.", file=sys.stderr)
        return 1

    for cmd in commands:
        print(f"\n>>> {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=BACKEND_ROOT, check=False)
        if result.returncode != 0:
            return result.returncode

    print("\nAll sample documents imported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
