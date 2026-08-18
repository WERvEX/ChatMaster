"""API request/response schemas (shared between routers and frontend types)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    request_id: UUID
    identity_id: str
    message: str = Field(min_length=1, max_length=20_000)
    history: list[MessageIn] = []
    conversation_id: str | None = None


class ConversationCreate(BaseModel):
    identity_id: str
    title: str | None = None


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


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
    request_id: str | None = None
    status: str = "complete"
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestFileResult(BaseModel):
    file: str
    chunks: int = 0
    error: str | None = None


class IngestResult(BaseModel):
    identity_id: str | None
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


class IngestSubmissionItem(BaseModel):
    file: str
    document_id: str
    job_id: str | None
    status: str
    duplicate: bool = False
    error: str | None = None


class IngestSubmission(BaseModel):
    items: list[IngestSubmissionItem]


class IndexVersionOut(BaseModel):
    id: str
    namespace: str
    identity_id: str | None
    logical_name: str
    collection_name: str
    embedding_provider: str
    embedding_model: str
    embedding_dim: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IndexRebuildRequest(BaseModel):
    target: Literal["private", "common"]
    identity_id: str | None = None
