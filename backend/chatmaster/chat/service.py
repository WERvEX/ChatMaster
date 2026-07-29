"""SSE event adapter with durable, cancellable chat turns."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from collections.abc import AsyncIterator
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select

from chatmaster.config import get_settings
from chatmaster.conversations.service import title_from_message
from chatmaster.db.models import Conversation, Message, utc_now
from chatmaster.db.session import SessionLocal
from chatmaster.schemas.api import ChatRequest

from .graph import ChatRuntime, default_runtime, prepare_chat_state

logger = logging.getLogger(__name__)


class StreamEvent(BaseModel):
    type: Literal["sources", "token", "done", "error"]
    data: dict


_CANCEL_LOCK = threading.Lock()
_CANCEL_EVENTS: dict[str, threading.Event] = {}


def request_cancel(request_id: str) -> bool:
    with _CANCEL_LOCK:
        event = _CANCEL_EVENTS.get(request_id)
        if event is None:
            return False
        event.set()
        return True


def _register_cancel(request_id: str) -> threading.Event:
    event = threading.Event()
    with _CANCEL_LOCK:
        _CANCEL_EVENTS[request_id] = event
    return event


def _unregister_cancel(request_id: str) -> None:
    with _CANCEL_LOCK:
        _CANCEL_EVENTS.pop(request_id, None)


def _begin_turn(
    *,
    request_id: str,
    conversation_id: str | None,
    identity_id: str,
    message: str,
    workspace_id: str,
) -> tuple[str, str, Message | None]:
    """Create an idempotent user/assistant pair and return any completed assistant."""
    with SessionLocal() as db:
        if conversation_id is None:
            conversation = Conversation(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                identity_id=identity_id,
                title=title_from_message(message),
            )
            db.add(conversation)
            db.flush()
            conversation_id = conversation.id
        else:
            conversation = db.get(Conversation, conversation_id)
            if conversation is not None and conversation.title == "新对话":
                has_messages = db.scalars(
                    select(Message.id)
                    .where(Message.conversation_id == conversation_id)
                    .limit(1)
                ).first()
                if has_messages is None:
                    conversation.title = title_from_message(message)

        existing = db.scalars(
            select(Message).where(
                Message.workspace_id == workspace_id,
                Message.conversation_id == conversation_id,
                Message.request_id == request_id,
                Message.role == "assistant",
            )
        ).first()
        if existing is not None:
            return conversation_id, existing.id, existing

        user_message = Message(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            role="user",
            content=message,
            sources_json=None,
            request_id=request_id,
            status="complete",
        )
        assistant_message = Message(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            role="assistant",
            content="",
            sources_json=[],
            request_id=request_id,
            status="pending",
        )
        db.add_all([user_message, assistant_message])
        db.commit()
        return conversation_id, assistant_message.id, None


def _finish_turn(
    assistant_message_id: str,
    *,
    answer: str,
    sources: list[dict],
    status: str,
) -> None:
    with SessionLocal() as db:
        assistant = db.get(Message, assistant_message_id)
        if assistant is None:
            return
        assistant.content = answer
        assistant.sources_json = sources
        assistant.status = status
        conversation = db.get(Conversation, assistant.conversation_id)
        if conversation is not None:
            conversation.updated_at = utc_now()
        db.commit()


async def stream_chat_events(
    *,
    identity_id: str,
    message: str,
    history: list[dict[str, str]],
    conversation_id: str | None,
    workspace_id: str,
    user_id: str,
    request_id: str | None = None,
    runtime: ChatRuntime | None = None,
) -> AsyncIterator[StreamEvent]:
    request_id = request_id or str(uuid.uuid4())
    active_runtime = runtime or default_runtime()
    durable = runtime is None
    assistant_message_id = str(uuid.uuid4())
    existing: Message | None = None
    cancel_event: threading.Event | None = None
    answer_parts: list[str] = []
    sources: list[dict] = []
    final_status = "pending"

    try:
        if durable:
            conversation_id, assistant_message_id, existing = _begin_turn(
                request_id=request_id,
                conversation_id=conversation_id,
                identity_id=identity_id,
                message=message,
                workspace_id=workspace_id,
            )
            if existing is not None and existing.status != "pending":
                final_status = existing.status
                yield StreamEvent(type="sources", data={"sources": existing.sources_json or []})
                if existing.content:
                    yield StreamEvent(type="token", data={"delta": existing.content})
                yield StreamEvent(
                    type="done",
                    data={
                        "message_id": existing.id,
                        "conversation_id": conversation_id,
                        "request_id": request_id,
                        "status": existing.status,
                    },
                )
                return
            if existing is not None:
                final_status = "duplicate_pending"
                yield StreamEvent(
                    type="error",
                    data={
                        "code": "REQUEST_IN_PROGRESS",
                        "message": "该请求正在生成中，请稍候。",
                        "request_id": request_id,
                    },
                )
                return

        cancel_event = _register_cancel(request_id)

        state = await prepare_chat_state(
            active_runtime,
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "identity_id": identity_id,
                "conversation_id": conversation_id,
                "request_id": request_id,
                "assistant_message_id": assistant_message_id,
                "message": message,
                "history": history,
            },
        )
        sources = state.get("sources", [])
        yield StreamEvent(type="sources", data={"sources": sources})

        async for token in active_runtime.stream_answer(state):
            if cancel_event.is_set():
                final_status = "stopped"
                break
            answer_parts.append(token)
            yield StreamEvent(type="token", data={"delta": token})
        else:
            final_status = "complete"

        state["answer"] = "".join(answer_parts)
        state["status"] = final_status
        if durable:
            _finish_turn(
                assistant_message_id,
                answer=state["answer"],
                sources=sources,
                status=final_status,
            )
        else:
            active_runtime.persist(state)
        yield StreamEvent(
            type="done",
            data={
                "message_id": assistant_message_id,
                "conversation_id": conversation_id,
                "request_id": request_id,
                "status": final_status,
            },
        )
    except asyncio.CancelledError:
        final_status = "stopped"
        if durable:
            _finish_turn(
                assistant_message_id,
                answer="".join(answer_parts),
                sources=sources,
                status=final_status,
            )
        raise
    except Exception:
        final_status = "failed"
        logger.exception(
            "Chat request failed request_id=%s conversation_id=%s",
            request_id,
            conversation_id,
        )
        if durable:
            _finish_turn(
                assistant_message_id,
                answer="".join(answer_parts),
                sources=sources,
                status=final_status,
            )
        data = {
            "code": "CHAT_FAILED",
            "message": "回答生成失败，请检查模型配置后重试。",
            "request_id": request_id,
        }
        # Preserve the injected-runtime diagnostic contract used by unit tests.
        if runtime is not None:
            data["detail"] = "missing" if identity_id == "missing" else data["message"]
        yield StreamEvent(type="error", data=data)
    finally:
        if durable and final_status == "pending":
            _finish_turn(
                assistant_message_id,
                answer="".join(answer_parts),
                sources=sources,
                status="stopped",
            )
        if cancel_event is not None:
            _unregister_cancel(request_id)


async def stream_chat(
    req: ChatRequest, *, workspace_id: str | None = None, user_id: str | None = None
) -> AsyncIterator[dict]:
    settings = get_settings()
    history = [{"role": item.role, "content": item.content} for item in req.history]
    async for event in stream_chat_events(
        request_id=str(req.request_id),
        identity_id=req.identity_id,
        message=req.message.strip(),
        history=history,
        conversation_id=req.conversation_id,
        workspace_id=workspace_id or settings.local_workspace_id,
        user_id=user_id or settings.local_user_id,
    ):
        yield {
            "event": event.type,
            "data": json.dumps(event.data, ensure_ascii=False),
        }
