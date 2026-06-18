"""The RAG chain: retrieve -> augment prompt -> stream tokens.

Structure intentionally mirrors future LangGraph nodes
(retrieve -> augment -> generate) so migrating to a StateGraph is mechanical.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from chatmaster.ai.models import build_chat_model, build_embeddings
from chatmaster.ai.prompts import build_prompt, format_context
from chatmaster.ai.retriever import retrieve
from chatmaster.identities.schema import IdentityConfig


class SourceItem(BaseModel):
    n: int
    source_file: str
    collection: str
    score: float


class StreamEvent(BaseModel):
    """One event in the chat stream."""

    type: Literal["sources", "token", "done", "error"]
    data: dict


def _history_to_messages(history: list[dict]) -> list:
    msgs = []
    for m in history:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "assistant":
            msgs.append(AIMessage(content=content))
        else:
            msgs.append(HumanMessage(content=content))
    return msgs


async def astream_chat(
    identity: IdentityConfig,
    message: str,
    history: list[dict],
) -> AsyncIterator[StreamEvent]:
    """Yield StreamEvents: one `sources`, many `token`, one terminal `done`/`error`."""
    message_id = str(uuid.uuid4())
    try:
        # --- retrieve ---
        embeddings = build_embeddings(identity)
        chunks = await retrieve(identity, message, embeddings)

        sources = [
            SourceItem(
                n=i,
                source_file=c.source_file,
                collection=c.collection,
                score=round(c.score, 6),
            ).model_dump()
            for i, c in enumerate(chunks, start=1)
        ]
        yield StreamEvent(type="sources", data={"sources": sources})

        # --- augment + generate ---
        chat_model = build_chat_model(identity)
        prompt = build_prompt(identity.system_prompt)
        chain = prompt | chat_model

        messages = prompt.format_messages(
            system_prompt=identity.system_prompt,
            context=format_context(chunks),
            history=_history_to_messages(history),
            message=message,
        )

        async for chunk in chat_model.astream(messages):
            token = chunk.content if isinstance(chunk.content, str) else ""
            if token:
                yield StreamEvent(type="token", data={"delta": token})

        yield StreamEvent(type="done", data={"message_id": message_id})
    except Exception as e:  # noqa: BLE001 - surface as a stream error event
        yield StreamEvent(type="error", data={"detail": str(e)})
