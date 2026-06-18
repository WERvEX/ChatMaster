"""AI orchestration layer (LangChain). No FastAPI dependency here."""

from chatmaster.ai.chain import StreamEvent, astream_chat
from chatmaster.ai.loaders import UnsupportedFileType, load_file
from chatmaster.ai.models import build_chat_model, build_embeddings
from chatmaster.ai.retriever import RetrievedChunk, retrieve
from chatmaster.ai.vectorstore import ensure_all_collections, get_store

__all__ = [
    "StreamEvent",
    "UnsupportedFileType",
    "RetrievedChunk",
    "astream_chat",
    "build_chat_model",
    "build_embeddings",
    "ensure_all_collections",
    "get_store",
    "load_file",
    "retrieve",
]
