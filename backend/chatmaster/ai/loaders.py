"""Dispatch files to the right LangChain DocumentLoader by extension."""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


class UnsupportedFileType(ValueError):
    pass


def load_file(path: Path, *, identity_id: str) -> list[Document]:
    """Load a single file into LangChain Documents, tagged with source metadata."""
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileType(f"Unsupported file type: {path.suffix}")

    if ext in {".txt", ".md"}:
        from langchain_community.document_loaders import TextLoader

        docs = TextLoader(str(path), encoding="utf-8").load()
    elif ext == ".pdf":
        from langchain_community.document_loaders import PyPDFLoader

        docs = PyPDFLoader(str(path)).load()
    elif ext == ".docx":
        from langchain_community.document_loaders import Docx2txtLoader

        docs = Docx2txtLoader(str(path)).load()
    else:  # pragma: no cover - guarded above
        raise UnsupportedFileType(ext)

    # Tag every chunk with provenance metadata.
    for d in docs:
        d.metadata.setdefault("source_file", path.name)
        d.metadata["identity_id"] = identity_id
    return docs
