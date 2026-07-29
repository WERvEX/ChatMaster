"""Chat endpoint: POST /api/chat streams SSE (token / sources / done / error)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from chatmaster.conversations.service import ConversationNotFound, get_conversation
from chatmaster.core.auth import get_current_user_id, get_current_workspace_id
from chatmaster.db.session import get_db
from chatmaster.identities.service import IdentityNotFound, get_identity_model
from chatmaster.schemas.api import ChatRequest
from chatmaster.chat.service import request_cancel, stream_chat

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat/{request_id}/cancel")
async def cancel_chat(request_id: str):
    return {"request_id": request_id, "cancelled": request_cancel(request_id)}


@router.post("/chat")
async def chat(
    req: ChatRequest,
    workspace_id: str = Depends(get_current_workspace_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Validate identity up front so a 404 is returned cleanly (not as an SSE error).
    try:
        get_identity_model(db, workspace_id=workspace_id, identity_id=req.identity_id)
    except IdentityNotFound:
        raise HTTPException(status_code=404, detail=f"Identity '{req.identity_id}' not found")
    if req.conversation_id:
        try:
            conversation = get_conversation(
                db, workspace_id=workspace_id, conversation_id=req.conversation_id
            )
        except ConversationNotFound:
            raise HTTPException(status_code=404, detail="Conversation not found") from None
        if conversation.identity_id != req.identity_id:
            raise HTTPException(status_code=409, detail="Conversation belongs to another identity")

    async def gen():
        async for sse_str in stream_chat(req, workspace_id=workspace_id, user_id=user_id):
            yield sse_str

    return EventSourceResponse(gen())
