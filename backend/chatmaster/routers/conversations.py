"""Conversation endpoints for local demo persistence."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from chatmaster.conversations.service import (
    ConversationNotFound,
    create_conversation,
    delete_conversation,
    list_conversations,
    list_messages,
)
from chatmaster.core.auth import get_current_workspace_id
from chatmaster.db.session import get_db
from chatmaster.identities.loader import IdentityNotFound
from chatmaster.schemas.api import ConversationCreate, ConversationOut, MessageOut

router = APIRouter(tags=["conversations"])


@router.post("/api/conversations", response_model=ConversationOut)
def post_conversation(
    body: ConversationCreate,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    try:
        conversation = create_conversation(
            db,
            workspace_id=workspace_id,
            identity_id=body.identity_id,
            title=body.title,
        )
    except IdentityNotFound:
        raise HTTPException(
            status_code=404, detail=f"Identity '{body.identity_id}' not found"
        ) from None
    return conversation


@router.get("/api/conversations", response_model=list[ConversationOut])
def get_conversations(
    identity_id: str | None = Query(None),
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    return list_conversations(db, workspace_id=workspace_id, identity_id=identity_id)


@router.get("/api/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_conversation_messages(
    conversation_id: str,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    try:
        return list_messages(
            db, workspace_id=workspace_id, conversation_id=conversation_id
        )
    except ConversationNotFound:
        raise HTTPException(status_code=404, detail="Conversation not found") from None


@router.delete("/api/conversations/{conversation_id}", status_code=204)
def remove_conversation(
    conversation_id: str,
    workspace_id: str = Depends(get_current_workspace_id),
    db: Session = Depends(get_db),
):
    try:
        delete_conversation(
            db, workspace_id=workspace_id, conversation_id=conversation_id
        )
    except ConversationNotFound:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
