"""API request/response schemas (shared between routers and frontend types)."""

from __future__ import annotations

from pydantic import BaseModel


class MessageIn(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    identity_id: str
    message: str
    history: list[MessageIn] = []


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
