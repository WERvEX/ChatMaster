"""Chat service: thin adapter that maps the LangChain StreamEvent flow to SSE.

Yields dicts in the shape sse-starlette expects: {"event": ..., "data": ...}.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from chatmaster.ai.chain import astream_chat
from chatmaster.identities.loader import get_registry
from chatmaster.schemas.api import ChatRequest


async def stream_chat(req: ChatRequest) -> AsyncIterator[dict]:
    registry = get_registry()
    identity = registry.get(req.identity_id)  # raises IdentityNotFound -> 404 by router

    history = [{"role": m.role, "content": m.content} for m in req.history]

    async for ev in astream_chat(identity, req.message, history):
        yield {
            "event": ev.type,
            "data": json.dumps(ev.data, ensure_ascii=False),
        }
