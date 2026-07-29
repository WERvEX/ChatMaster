# ChatMaster Architecture

ChatMaster is currently optimized for local and small-team use. The code is structured so it can later move toward a multi-user deployable product without replacing the core architecture.

## Runtime Shape

- Frontend: React, Vite, TypeScript, React Router, TanStack Query.
- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic.
- Chat workflow: LangGraph for explicit RAG state transitions.
- Business database: SQLite by default.
- Vector database: Qdrant.
- File storage: local filesystem under `STORAGE_DIR`.

## Persistence

SQLite is the local default:

```dotenv
DATABASE_URL=sqlite:///./data/chatmaster.db
```

The schema is modeled with SQLAlchemy and Alembic so PostgreSQL can be introduced later by changing `DATABASE_URL` and running migrations. Tables already include `workspace_id` and local user/workspace boundaries to avoid a later multi-tenant rewrite.

Business data belongs in the relational database:

- workspaces
- users
- identities
- provider configs
- conversations
- messages
- documents
- document chunks
- ingest jobs
- index versions

Qdrant stores vectors and retrieval metadata copies. It is not the source of truth for documents, jobs, conversations, or provider configuration.

## RAG Flow

The chat path is split into explicit steps:

```text
load identity
load history
retrieve private/common context
build prompt messages
stream model answer
persist messages when conversation_id is present
```

`chatmaster.chat.graph` owns the LangGraph workflow. `chatmaster.chat.service` adapts graph state to SSE events.

Retrieval is isolated under `chatmaster.retrieval`:

- score-returning search where supported
- weighted RRF fusion
- final-window common chunk guarantee
- explicit `rank`, `dense_score`, and `fusion_score`
- vector dimension mismatch errors

## Documents

Uploads are streamed to durable storage before a background ingestion job is queued:

```text
data/storage/{workspace_id}/documents/{document_id}/{filename}
```

Each upload creates:

- a `documents` row
- an `ingest_jobs` row
- a stored file
- a restart-aware in-process background ingest job

The local executor uses a bounded thread pool. Pending/running jobs are resumed
after restart, and the public job API can later be backed by an external queue.

## Provider Config

Provider configuration is database-backed. API keys are encrypted with Fernet;
the encryption key remains an operator-managed environment secret and is only
required when encrypted credentials are stored or changed.

## Migrations

Run migrations from `backend/`:

```powershell
C:\Users\74511\miniconda3\envs\chatmaster\Scripts\alembic.exe upgrade head
```

Application startup runs Alembic migrations. A legacy database created with
`create_all()` is backed up, stamped at the detected baseline, and upgraded once.

## Rebuilding Indexes

Changing embedding provider, model, or vector dimension requires rebuilding affected Qdrant collections. Existing vectors are not compatible across dimensions.

The expected future flow is:

1. Create a new `index_versions` row.
2. Create or validate a matching Qdrant collection.
3. Re-embed document chunks.
4. Mark the new index version active.
5. Retire the old version after validation.

