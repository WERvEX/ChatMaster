"""API request/response schemas (shared between routers and frontend types)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MessageIn(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    identity_id: str
    message: str
    history: list[MessageIn] = []
    conversation_id: str | None = None


class ConversationCreate(BaseModel):
    identity_id: str
    title: str | None = None


class ConversationOut(BaseModel):
    id: str
    workspace_id: str
    identity_id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources_json: list[dict] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestFileResult(BaseModel):
    file: str
    chunks: int = 0
    error: str | None = None


class IngestResult(BaseModel):
    identity_id: str
    target: str
    collection: str
    files: list[IngestFileResult]
    total_chunks: int


class HealthOut(BaseModel):
    status: str
    providers: dict
    collections: list[str]
    identities: list[str]


class DocumentOut(BaseModel):
    id: str
    identity_id: str | None
    namespace: str
    filename: str
    content_type: str | None
    storage_path: str
    sha256: str
    status: str
    created_at: datetime
    updated_at: datetime


class IngestJobOut(BaseModel):
    id: str
    document_id: str
    status: str
    error: str | None
    total_chunks: int
    created_at: datetime
    updated_at: datetime
