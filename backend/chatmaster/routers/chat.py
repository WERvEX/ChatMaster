"""Chat endpoint: POST /api/chat streams SSE (token / sources / done / error)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from chatmaster.core.auth import get_current_user_id, get_current_workspace_id
from chatmaster.identities.loader import IdentityNotFound, get_registry
from chatmaster.schemas.api import ChatRequest
from chatmaster.services.chat_service import stream_chat

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(
    req: ChatRequest,
    workspace_id: str = Depends(get_current_workspace_id),
    user_id: str = Depends(get_current_user_id),
):
    _ = (workspace_id, user_id)
    # Validate identity up front so a 404 is returned cleanly (not as an SSE error).
    try:
        get_registry().get(req.identity_id)
    except IdentityNotFound:
        raise HTTPException(status_code=404, detail=f"Identity '{req.identity_id}' not found")

    async def gen():
        async for sse_str in stream_chat(req):
            yield sse_str

    return EventSourceResponse(gen())
