# ChatMaster Scheme B Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor ChatMaster into a local/small-team MVP architecture that remains easy to evolve into a multi-user deployable product.

**Architecture:** Keep FastAPI, React/Vite, and Qdrant. Add a relational business database with SQLite as the local runtime target and PostgreSQL-compatible modeling from the start. Move RAG orchestration into LangGraph while keeping document ingestion, retrieval, provider configuration, and persistence as ordinary service modules.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, SQLite now/PostgreSQL later, Qdrant, LangGraph, LangChain adapters, React, Vite, TypeScript, React Router, TanStack Query.

---

## Scope

This plan is intentionally split into phases. Phase 1 creates the durable backend foundation without rewriting the full UI. Phase 2 migrates chat/RAG to LangGraph. Phase 3 upgrades the frontend into a small-team workbench. Phase 4 hardens for future multi-user deployment.

Do not introduce PostgreSQL, Redis, object storage, or full authentication in the first implementation pass. Design the schema and service boundaries so those changes are additive later.

---

## Target File Structure

### Backend

- Create: `backend/chatmaster/core/config.py`  
  Owns application settings, database URL, storage paths, CORS, and provider defaults.

- Create: `backend/chatmaster/db/base.py`  
  Exposes SQLAlchemy declarative base and shared model metadata.

- Create: `backend/chatmaster/db/session.py`  
  Owns engine creation, session factory, and FastAPI DB dependency.

- Create: `backend/chatmaster/db/models.py`  
  Defines business tables: workspaces, users, identities, provider configs, conversations, messages, documents, document chunks, ingest jobs, index versions.

- Create: `backend/chatmaster/db/init_db.py`  
  Creates the local SQLite schema for demo use before Alembic is fully wired into the developer workflow.

- Create: `backend/alembic.ini` and `backend/alembic/env.py`  
  Adds migration support.

- Create: `backend/chatmaster/identities/service.py`  
  Moves identity read/write logic from YAML-only registry toward database-backed identities.

- Create: `backend/chatmaster/providers/service.py`  
  Stores provider config in the DB instead of `data/providers.json`, while preserving masked-key behavior.

- Create: `backend/chatmaster/documents/service.py`  
  Owns document records, file persistence metadata, ingest job creation, and status updates.

- Create: `backend/chatmaster/documents/parsers.py`  
  Moves file parsing from `ai/loaders.py` into the document domain.

- Create: `backend/chatmaster/documents/chunking.py`  
  Moves chunking from `ai/chunkers.py` into the document domain.

- Create: `backend/chatmaster/retrieval/vectorstore.py`  
  Owns Qdrant access, collection naming, vector dimension validation, and index version checks.

- Create: `backend/chatmaster/retrieval/retriever.py`  
  Owns private/common retrieval, score capture, fusion, and thresholding.

- Create: `backend/chatmaster/chat/graph.py`  
  Defines LangGraph state and nodes for load identity, load history, retrieve, build prompt, generate, and persist.

- Create: `backend/chatmaster/chat/service.py`  
  Adapts the graph event stream to SSE response events.

- Modify: `backend/chatmaster/main.py`  
  Initialize DB, include new routers, and stop forcing all initialization through the old identity registry.

- Modify: `backend/chatmaster/routers/*.py`  
  Gradually move routers to call domain services rather than `ai/*` modules directly.

- Keep temporarily: `backend/chatmaster/ai/*`  
  Treat existing modules as compatibility shims during migration. Remove only after feature parity is verified.

### Frontend

- Add: `frontend/src/routes/*`  
  Introduce page-level routing for chat, knowledge base, identities, and settings.

- Add: `frontend/src/api/queryClient.ts`  
  Configure TanStack Query.

- Add: `frontend/src/features/chat/*`  
  Move chat hooks and components under a feature boundary.

- Add: `frontend/src/features/knowledge/*`  
  Add document list, upload, and ingest job status.

- Add: `frontend/src/features/settings/*`  
  Move provider settings.

- Modify: `frontend/src/App.tsx`  
  Convert from one large shell into route layout plus navigation.

---

## Phase 1: Backend Foundation

### Task 1: Add SQLAlchemy and Alembic Dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] Add dependencies:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.8",
    "pydantic-settings>=2.5",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "langgraph>=0.2",
    "langchain>=0.3",
    "langchain-community>=0.3",
    "langchain-openai>=0.2",
    "langchain-anthropic>=0.2",
    "langchain-qdrant>=0.1",
    "langchain-text-splitters>=0.3",
    "qdrant-client>=1.12",
    "docx2txt>=0.1",
    "pypdf>=5.0",
    "typer>=0.12",
    "python-multipart>=0.0.9",
    "sse-starlette>=2.1",
    "pyyaml>=6.0",
]
```

- [ ] Run:

```powershell
cd C:\Workspace\ChatMaster\backend
python -m pip install -e ".[dev]"
```

Expected: package installs without resolver errors.

- [ ] Commit:

```powershell
git add backend/pyproject.toml
git commit -m "chore: add database and graph dependencies"
```

### Task 2: Introduce Database Settings

**Files:**
- Modify: `backend/chatmaster/config.py`
- Modify: `.env.example`

- [ ] Add settings:

```python
database_url: str = "sqlite:///./data/chatmaster.db"
storage_dir: str = "data/storage"
local_workspace_id: str = "local"
local_user_id: str = "local-user"
```

- [ ] Add `.env.example` values:

```dotenv
DATABASE_URL=sqlite:///./data/chatmaster.db
STORAGE_DIR=data/storage
LOCAL_WORKSPACE_ID=local
LOCAL_USER_ID=local-user
```

- [ ] Run:

```powershell
cd C:\Workspace\ChatMaster\backend
python -m compileall chatmaster
```

Expected: compile succeeds.

- [ ] Commit:

```powershell
git add backend/chatmaster/config.py .env.example
git commit -m "chore: add local database settings"
```

### Task 3: Add SQLAlchemy Session Infrastructure

**Files:**
- Create: `backend/chatmaster/db/__init__.py`
- Create: `backend/chatmaster/db/base.py`
- Create: `backend/chatmaster/db/session.py`

- [ ] Create `base.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] Create `session.py`:

```python
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from chatmaster.config import get_settings


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args=_connect_args(settings.database_url),
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] Run:

```powershell
cd C:\Workspace\ChatMaster\backend
python -m compileall chatmaster\db
```

Expected: compile succeeds.

- [ ] Commit:

```powershell
git add backend/chatmaster/db
git commit -m "feat: add database session infrastructure"
```

### Task 4: Define Business Data Model

**Files:**
- Create: `backend/chatmaster/db/models.py`

- [ ] Define these tables with SQLAlchemy 2.0 typed models:

```text
Workspace
User
Identity
ProviderConfig
Conversation
Message
Document
DocumentChunk
IngestJob
IndexVersion
```

- [ ] Required model fields:

```text
All tenant-owned tables:
- id
- workspace_id
- created_at
- updated_at where mutation is expected

Identity:
- id
- workspace_id
- slug
- name
- description
- system_prompt
- private_collection
- generation_model
- embedding_model
- retrieval_config_json
- is_active

ProviderConfig:
- id
- workspace_id
- chat_provider
- chat_base_url
- chat_api_key_encrypted
- chat_model
- embedding_provider
- embedding_base_url
- embedding_api_key_encrypted
- embedding_model
- huggingface_endpoint

Conversation:
- id
- workspace_id
- identity_id
- title

Message:
- id
- workspace_id
- conversation_id
- role
- content
- sources_json

Document:
- id
- workspace_id
- identity_id nullable for common docs
- namespace private/common
- filename
- content_type
- storage_path
- sha256
- status

DocumentChunk:
- id
- workspace_id
- document_id
- index_version_id
- qdrant_point_id
- chunk_index
- text
- metadata_json

IngestJob:
- id
- workspace_id
- document_id
- status
- error
- total_chunks

IndexVersion:
- id
- workspace_id
- namespace
- identity_id nullable
- collection_name
- embedding_provider
- embedding_model
- embedding_dim
- status
```

- [ ] Add uniqueness constraints:

```text
Identity: workspace_id + slug
ProviderConfig: workspace_id
Document: workspace_id + sha256 + namespace + identity_id
IndexVersion: workspace_id + collection_name
```

- [ ] Add tests later in Task 6 after init infrastructure exists.

- [ ] Commit:

```powershell
git add backend/chatmaster/db/models.py
git commit -m "feat: define business database models"
```

### Task 5: Add Local DB Initialization

**Files:**
- Create: `backend/chatmaster/db/init_db.py`
- Modify: `backend/chatmaster/main.py`

- [ ] Create `init_db.py`:

```python
from __future__ import annotations

from chatmaster.db.base import Base
from chatmaster.db.session import engine


def init_db() -> None:
    from chatmaster.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
```

- [ ] In `main.py` lifespan, call `init_db()` before loading runtime services.

- [ ] Run:

```powershell
cd C:\Workspace\ChatMaster\backend
python -m compileall chatmaster
```

Expected: compile succeeds.

- [ ] Commit:

```powershell
git add backend/chatmaster/db/init_db.py backend/chatmaster/main.py
git commit -m "feat: initialize local database on startup"
```

### Task 6: Add Database Model Tests

**Files:**
- Create: `backend/tests/db/test_models.py`

- [ ] Add tests that create an in-memory SQLite engine, create all tables, insert:

```text
one workspace
one user
one identity
one provider config
one conversation
one user message
one assistant message
one document
one index version
one document chunk
one ingest job
```

- [ ] Test uniqueness for identity slug inside the same workspace.

- [ ] Run:

```powershell
cd C:\Workspace\ChatMaster\backend
pytest tests\db\test_models.py -v
```

Expected: all tests pass.

- [ ] Commit:

```powershell
git add backend/tests/db/test_models.py
git commit -m "test: cover database model relationships"
```

---

## Phase 2: Migrate Runtime Configuration and Identities

### Task 7: Seed Local Workspace and Default Identities

**Files:**
- Create: `backend/chatmaster/db/seed.py`
- Modify: `backend/chatmaster/main.py`

- [ ] Seed local workspace/user from settings if missing.

- [ ] Read existing `backend/chatmaster/identities/identities.yaml`.

- [ ] Upsert each identity into the `identities` table by `workspace_id + slug`.

- [ ] Keep YAML as seed data only; runtime reads should move to DB.

- [ ] Run:

```powershell
cd C:\Workspace\ChatMaster\backend
python -m compileall chatmaster
```

Expected: compile succeeds.

- [ ] Commit:

```powershell
git add backend/chatmaster/db/seed.py backend/chatmaster/main.py
git commit -m "feat: seed local workspace and identities"
```

### Task 8: Move Provider Config to Database

**Files:**
- Create: `backend/chatmaster/providers/__init__.py`
- Create: `backend/chatmaster/providers/service.py`
- Modify: `backend/chatmaster/ai/providers.py`
- Modify: `backend/chatmaster/routers/providers.py`

- [ ] Implement provider service methods:

```text
get_provider_config(db, workspace_id)
save_provider_config(db, workspace_id, payload)
mask_key(key)
is_masked(key)
```

- [ ] Preserve current behavior:

```text
GET returns masked keys.
PUT keeps existing keys if payload key is empty or masked.
Fallback seed values still come from .env when no DB row exists.
Saving provider config clears model and vector store caches.
```

- [ ] Add tests:

```text
GET masks keys.
PUT with masked key keeps previous secret.
PUT with new key replaces previous secret.
```

- [ ] Commit:

```powershell
git add backend/chatmaster/providers backend/chatmaster/ai/providers.py backend/chatmaster/routers/providers.py backend/tests
git commit -m "feat: persist provider config in database"
```

---

## Phase 3: RAG and LangGraph Refactor

### Task 9: Introduce Retrieval Service with Score Semantics

**Files:**
- Create: `backend/chatmaster/retrieval/__init__.py`
- Create: `backend/chatmaster/retrieval/schemas.py`
- Create: `backend/chatmaster/retrieval/vectorstore.py`
- Create: `backend/chatmaster/retrieval/retriever.py`
- Modify: `backend/chatmaster/ai/retriever.py`

- [ ] Retrieval result must expose:

```text
text
source_file
collection
rank
dense_score
fusion_score
metadata
```

- [ ] Replace `asimilarity_search()` with a score-returning search API where supported.

- [ ] Fix common chunk guarantee so `min_chunks_common` is calculated after selecting the top candidate window.

- [ ] Add vector dimension validation:

```text
If collection exists and vector size differs from current embedding dim, raise a clear error telling the user to rebuild the index.
```

- [ ] Add tests:

```text
weighted RRF orders private/common results correctly
min_chunks_common is enforced in final top_k
duplicate chunks are fused by stable id
dimension mismatch raises explicit error
```

- [ ] Commit:

```powershell
git add backend/chatmaster/retrieval backend/chatmaster/ai/retriever.py backend/tests
git commit -m "feat: add retrieval service with explicit scores"
```

### Task 10: Add LangGraph Chat Workflow

**Files:**
- Create: `backend/chatmaster/chat/__init__.py`
- Create: `backend/chatmaster/chat/state.py`
- Create: `backend/chatmaster/chat/graph.py`
- Create: `backend/chatmaster/chat/service.py`
- Modify: `backend/chatmaster/routers/chat.py`

- [ ] Define graph state:

```text
workspace_id
user_id
identity_id
conversation_id
message
history
retrieved_chunks
context
answer
sources
error
```

- [ ] Define graph nodes:

```text
load_identity
load_history
retrieve_context
build_messages
generate_answer
persist_messages
```

- [ ] Preserve SSE event contract:

```text
sources
token
done
error
```

- [ ] Persist user and assistant messages when `conversation_id` is present.

- [ ] Add tests:

```text
chat graph emits sources before tokens
chat graph persists user and assistant messages
unknown identity returns clear error
```

- [ ] Commit:

```powershell
git add backend/chatmaster/chat backend/chatmaster/routers/chat.py backend/tests
git commit -m "feat: route chat through LangGraph workflow"
```

---

## Phase 4: Documents and Ingestion

### Task 11: Add Document Records and Local Storage

**Files:**
- Create: `backend/chatmaster/documents/__init__.py`
- Create: `backend/chatmaster/documents/service.py`
- Create: `backend/chatmaster/documents/parsers.py`
- Create: `backend/chatmaster/documents/chunking.py`
- Modify: `backend/chatmaster/routers/documents.py`

- [ ] Store uploaded files under:

```text
data/storage/{workspace_id}/documents/{document_id}/{original_filename}
```

- [ ] Create document row before parsing.

- [ ] Create ingest job row.

- [ ] Parse, chunk, embed, and upsert synchronously for Phase 1 compatibility.

- [ ] Update job status to `completed` or `failed`.

- [ ] Add tests:

```text
upload creates document row
upload creates ingest job row
unsupported extension returns 400
oversized file returns 413
```

- [ ] Commit:

```powershell
git add backend/chatmaster/documents backend/chatmaster/routers/documents.py backend/tests
git commit -m "feat: persist documents and ingest jobs"
```

### Task 12: Add Document and Job Listing APIs

**Files:**
- Modify: `backend/chatmaster/routers/documents.py`
- Modify: `backend/chatmaster/schemas/api.py`

- [ ] Add endpoints:

```text
GET /api/documents
GET /api/documents/{document_id}
GET /api/ingest-jobs
GET /api/ingest-jobs/{job_id}
```

- [ ] Support filters:

```text
identity_id
namespace private/common
status
```

- [ ] Add tests for each endpoint.

- [ ] Commit:

```powershell
git add backend/chatmaster/routers/documents.py backend/chatmaster/schemas/api.py backend/tests
git commit -m "feat: expose document and ingest job APIs"
```

---

## Phase 5: Frontend Workbench Refactor

### Task 13: Add Routing and Query Client

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/api/queryClient.ts`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] Add dependencies:

```powershell
cd C:\Workspace\ChatMaster\frontend
npm.cmd install @tanstack/react-query react-router-dom
```

- [ ] Wrap app with `QueryClientProvider`.

- [ ] Add routes:

```text
/chat
/knowledge
/identities
/settings
```

- [ ] Run:

```powershell
cd C:\Workspace\ChatMaster\frontend
npm.cmd run build
```

Expected: TypeScript and Vite build pass.

- [ ] Commit:

```powershell
git add frontend/package.json frontend/package-lock.json frontend/src
git commit -m "feat: add frontend routing and query client"
```

### Task 14: Split Chat Feature

**Files:**
- Create: `frontend/src/features/chat/*`
- Move: `frontend/src/hooks/useChat.ts`
- Move: `frontend/src/components/ChatWindow.tsx`
- Move: `frontend/src/components/ChatMessage.tsx`
- Move: `frontend/src/components/ChatInput.tsx`
- Move: `frontend/src/components/SourceList.tsx`

- [ ] Preserve current chat behavior.

- [ ] Add optional `conversation_id` to chat request types.

- [ ] Keep SSE client behavior unchanged.

- [ ] Run:

```powershell
cd C:\Workspace\ChatMaster\frontend
npm.cmd run build
```

Expected: build passes.

- [ ] Commit:

```powershell
git add frontend/src
git commit -m "refactor: isolate chat frontend feature"
```

### Task 15: Add Knowledge Base Page

**Files:**
- Create: `frontend/src/features/knowledge/*`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/types/api.ts`

- [ ] Add document list using `GET /api/documents`.

- [ ] Keep upload form and show ingest result.

- [ ] Add job status table using `GET /api/ingest-jobs`.

- [ ] Run:

```powershell
cd C:\Workspace\ChatMaster\frontend
npm.cmd run build
```

Expected: build passes.

- [ ] Commit:

```powershell
git add frontend/src
git commit -m "feat: add knowledge base management page"
```

---

## Phase 6: Hardening and Migration Readiness

### Task 16: Add Alembic Baseline Migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/<revision>_baseline.py`

- [ ] Configure Alembic to read `DATABASE_URL`.

- [ ] Generate baseline migration from SQLAlchemy metadata.

- [ ] Verify:

```powershell
cd C:\Workspace\ChatMaster\backend
alembic upgrade head
```

Expected: local SQLite database upgrades successfully.

- [ ] Commit:

```powershell
git add backend/alembic.ini backend/alembic
git commit -m "chore: add alembic baseline migration"
```

### Task 17: Add Local Auth Placeholder

**Files:**
- Create: `backend/chatmaster/core/auth.py`
- Modify: routers to use current workspace/user dependency

- [ ] Implement dependency:

```text
get_current_workspace_id() -> settings.local_workspace_id
get_current_user_id() -> settings.local_user_id
```

- [ ] Use these dependencies in chat, documents, identities, and providers routers.

- [ ] Do not implement login yet.

- [ ] Commit:

```powershell
git add backend/chatmaster/core/auth.py backend/chatmaster/routers
git commit -m "chore: add local auth boundary"
```

### Task 18: Add Project Documentation

**Files:**
- Create: `docs/architecture.md`
- Modify: `README.md`

- [ ] Document:

```text
local/small-team deployment target
SQLite now, PostgreSQL later
Qdrant role
LangGraph role
module boundaries
how to run migrations
how to rebuild indexes after embedding changes
```

- [ ] Commit:

```powershell
git add docs/architecture.md README.md
git commit -m "docs: describe refactored architecture"
```

---

## Verification Checklist

- [ ] Backend compiles:

```powershell
cd C:\Workspace\ChatMaster\backend
python -m compileall chatmaster
```

- [ ] Backend tests pass:

```powershell
cd C:\Workspace\ChatMaster\backend
pytest -v
```

- [ ] Frontend builds:

```powershell
cd C:\Workspace\ChatMaster\frontend
npm.cmd run build
```

- [ ] Manual smoke test:

```text
Start Qdrant.
Start backend.
Start frontend.
Open chat page.
Select legal_expert.
Upload a txt file.
Ask a question covered by the file.
Verify sources appear before streamed answer.
Open knowledge page.
Verify document and ingest job are listed.
Open provider settings.
Verify masked keys are preserved on save.
```

---

## Execution Recommendation

Execute in this order:

1. Phase 1 only: database foundation.
2. Verify backend still starts and existing chat still works.
3. Phase 2: provider and identity DB migration.
4. Verify provider save/test and identity list.
5. Phase 3: retrieval and LangGraph.
6. Verify RAG quality with sample docs.
7. Phase 4: document persistence.
8. Phase 5: frontend workbench.
9. Phase 6: hardening and docs.

Do not start Phase 5 before Phases 1-4 are stable. The frontend should consume stable APIs rather than chase backend changes.
