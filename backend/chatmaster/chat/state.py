"""State passed through the chat LangGraph workflow."""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import BaseMessage

from chatmaster.identities.schema import IdentityConfig
from chatmaster.retrieval.schemas import RetrievedChunk


class ChatState(TypedDict, total=False):
    workspace_id: str
    user_id: str
    identity_id: str
    conversation_id: str | None
    message: str
    history: list[dict[str, str]]
    identity: IdentityConfig
    retrieved_chunks: list[RetrievedChunk]
    messages: list[BaseMessage]
    answer: str
    sources: list[dict[str, Any]]
    error: str

