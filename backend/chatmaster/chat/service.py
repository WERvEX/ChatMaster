"""SSE event adapter for the LangGraph chat workflow."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Literal

from pydantic import BaseModel

from chatmaster.config import get_settings
from chatmaster.db.session import SessionLocal
from chatmaster.schemas.api import ChatRequest

from .graph import ChatRuntime, default_runtime, persist_messages, prepare_chat_state
from .state import ChatState


class StreamEvent(BaseModel):
    type: Literal["sources", "token", "done", "error"]
    data: dict


def _runtime_with_db_persistence(runtime: ChatRuntime | None = None) -> ChatRuntime:
    if runtime is not None:
        return runtime

    base = default_runtime()

    def persist(state: ChatState) -> None:
        base.persist(state)
        if state.get("conversation_id"):
            with SessionLocal() as db:
                persist_messages(db, state)

    return ChatRuntime(
        load_identity=base.load_identity,
        load_history=base.load_history,
        retrieve=base.retrieve,
        stream_answer=base.stream_answer,
        persist=persist,
    )


async def stream_chat_events(
    *,
    identity_id: str,
    message: str,
    history: list[dict[str, str]],
    conversation_id: str | None,
    workspace_id: str,
    user_id: str,
    runtime: ChatRuntime | None = None,
) -> AsyncIterator[StreamEvent]:
    active_runtime = _runtime_with_db_persistence(runtime)
    try:
        state = await prepare_chat_state(
            active_runtime,
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "identity_id": identity_id,
                "conversation_id": conversation_id,
                "message": message,
                "history": history,
            },
        )

        yield StreamEvent(type="sources", data={"sources": state.get("sources", [])})

        answer_parts: list[str] = []
        async for token in active_runtime.stream_answer(state):
            answer_parts.append(token)
            yield StreamEvent(type="token", data={"delta": token})

        state["answer"] = "".join(answer_parts)
        active_runtime.persist(state)
        yield StreamEvent(type="done", data={"message_id": str(uuid.uuid4())})
    except Exception as exc:  # noqa: BLE001 - stream errors must stay in-band
        yield StreamEvent(type="error", data={"detail": str(exc)})


async def stream_chat(req: ChatRequest) -> AsyncIterator[dict]:
    settings = get_settings()
    history = [{"role": item.role, "content": item.content} for item in req.history]
    async for event in stream_chat_events(
        identity_id=req.identity_id,
        message=req.message,
        history=history,
        conversation_id=req.conversation_id,
        workspace_id=settings.local_workspace_id,
        user_id=settings.local_user_id,
    ):
        yield {
            "event": event.type,
            "data": json.dumps(event.data, ensure_ascii=False),
        }
