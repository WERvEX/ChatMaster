"""Backward-compatible import location for chat SSE streaming."""

from __future__ import annotations

from collections.abc import AsyncIterator

from chatmaster.chat.service import stream_chat as _stream_chat
from chatmaster.schemas.api import ChatRequest


async def stream_chat(req: ChatRequest) -> AsyncIterator[dict]:
    async for event in _stream_chat(req):
        yield event
