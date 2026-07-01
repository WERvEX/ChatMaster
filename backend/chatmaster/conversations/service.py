"""Conversation CRUD and history loading."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from chatmaster.db.models import Conversation, Message
from chatmaster.identities.loader import IdentityNotFound, get_registry


class ConversationNotFound(KeyError):
    """Raised when a conversation does not exist in the workspace."""


def create_conversation(
    db: Session,
    *,
    workspace_id: str,
    identity_id: str,
    title: str | None = None,
) -> Conversation:
    get_registry().get(identity_id)  # raises IdentityNotFound
    conversation = Conversation(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        identity_id=identity_id,
        title=title or "新对话",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(
    db: Session,
    *,
    workspace_id: str,
    identity_id: str | None = None,
) -> list[Conversation]:
    stmt = select(Conversation).where(Conversation.workspace_id == workspace_id)
    if identity_id:
        stmt = stmt.where(Conversation.identity_id == identity_id)
    return list(db.execute(stmt.order_by(Conversation.updated_at.desc())).scalars())


def get_conversation(db: Session, *, workspace_id: str, conversation_id: str) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.workspace_id != workspace_id:
        raise ConversationNotFound(conversation_id)
    return conversation


def list_messages(
    db: Session,
    *,
    workspace_id: str,
    conversation_id: str,
) -> list[Message]:
    get_conversation(db, workspace_id=workspace_id, conversation_id=conversation_id)
    stmt = (
        select(Message)
        .where(
            Message.workspace_id == workspace_id,
            Message.conversation_id == conversation_id,
        )
        .order_by(Message.created_at)
    )
    return list(db.execute(stmt).scalars())


def load_history(
    db: Session,
    *,
    workspace_id: str,
    conversation_id: str,
) -> list[dict[str, str]]:
    messages = list_messages(
        db, workspace_id=workspace_id, conversation_id=conversation_id
    )
    return [{"role": message.role, "content": message.content} for message in messages]


def delete_conversation(db: Session, *, workspace_id: str, conversation_id: str) -> None:
    conversation = get_conversation(db, workspace_id=workspace_id, conversation_id=conversation_id)
    db.delete(conversation)
    db.commit()


def title_from_message(message: str, max_len: int = 30) -> str:
    text = message.strip().replace("\n", " ")
    if len(text) <= max_len:
        return text or "新对话"
    return text[: max_len - 1] + "…"
