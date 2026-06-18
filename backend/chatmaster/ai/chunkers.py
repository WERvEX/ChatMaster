"""Text chunking via LangChain's RecursiveCharacterTextSplitter (CJK-aware)."""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from chatmaster.config import get_settings

# CJK-aware separators: try paragraph, line, then CJK sentence punctuation,
# then ASCII period, then space, then char-level as last resort.
_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", ". ", " ", ""]


def build_splitter() -> RecursiveCharacterTextSplitter:
    s = get_settings()
    return RecursiveCharacterTextSplitter(
        chunk_size=s.chunk_size,
        chunk_overlap=s.chunk_overlap,
        separators=_SEPARATORS,
    )


def split_documents(docs: list[Document]) -> list[Document]:
    """Split documents into chunks; source_file metadata is preserved per chunk."""
    return build_splitter().split_documents(docs)
