# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read first

Two per-workspace manuals already exist and are authoritative for their side of the stack. **Read the relevant one before editing:**

- [backend/AGENTS.md](backend/AGENTS.md) — stack invariants, SSE wire protocol, DB/session rules, security gates, test matrix.
- [frontend/AGENTS.md](frontend/AGENTS.md) — component layout, SSE client contract, localStorage schema, theming, admin tab routing.

Deeper specs live in [backend/docs/](backend/docs/) and [frontend/docs/](frontend/docs/).

A test enforces documentation hygiene ([test_agent_docs_integrity.py](backend/tests/test_agent_docs_integrity.py)): both `AGENTS.md` files must stay **strictly under 200 lines**, the four files under `backend/docs/` and `frontend/docs/` must each exceed 50 lines, and specific legacy frontend components must remain deleted. Adding content to an `AGENTS.md` usually means moving something out to `docs/`.

## Commands

Run from the repo root unless noted. `.mise.toml` pins python 3.11 / node 20 / pnpm.

```bash
# Backend tests (venv is committed at backend/.venv; 136 tests must pass)
backend/.venv/bin/pytest backend/tests -q
backend/.venv/bin/pytest backend/tests/test_virtual_queue.py -v          # one module
backend/.venv/bin/pytest backend/tests/test_redis_cache.py::test_name -v # one test

# Backend dev server (from backend/, venv activated)
uvicorn app.main:app --reload --port 8000        # Swagger at :8000/docs

# Seed the official regulations into the vector store
python -m app.scripts.seed_db
python -m app.scripts.reindex_knowledge_base

# Frontend (from frontend/, pnpm@9.5.0 enforced)
pnpm dev
pnpm lint
./node_modules/.bin/next build                   # the real verification: TS + ESLint

# Full stack
docker compose up -d --build                     # :3000 app, :8000 API, :5432 postgres
docker compose --profile tunnel up -d            # + cloudflared
```

There is no frontend test suite — `next build` is the gate.

## Architecture

A Spanish-language RAG assistant answering graduation questions for Ingeniería de Sistemas at Universidad Distrital, plus an admin CRM that governs which regulations the RAG may cite.

**Two audiences, one backend.** Student chat (`/`) is anonymous and streamed; the admin CRM (`/admin`) is JWT-gated and manages the corpus. Both talk to the same FastAPI app, mounted under `/api/v1` in [app/api/router.py](backend/app/api/router.py): `auth`, `chat`, `admin`, `documents`, `webhooks`.

**Request path for a student question** — [app/api/v1/chat.py](backend/app/api/v1/chat.py) `POST /chat/stream` is the hot path and the single largest source of invariants. Five *zero-token* gates run before any LLM or embedding call, each short-circuiting into its own SSE generator: 24h ban check → rate limit (10/min) → prompt-injection/abuse gate (3 strikes = 24h ban) → benign-greeting gate → hybrid cache (L1 exact SHA-256, L2 semantic cosine ≥ 0.95). Only then does the request acquire a permit from the 150-slot semaphore, queueing in a FIFO [virtual_queue.py](backend/app/core/virtual_queue.py) (cap 100, 15s wait) and emitting `queue`/`queue_ready` frames, before [rag_service.py](backend/app/services/rag_service.py) retrieves chunks and streams tokens.

**Permits and sessions are the two things that break under load.** Every semaphore permit must be held by `SemaphoreReleaseGuard` and every release must call `virtual_queue.notify_available()`. Request-scoped `Depends(get_db)` sessions must never cross into SSE generators or worker threads — those create their own `SessionLocal()` with `finally: db.close()`.

**Regulatory lineage is the point of the CRM.** `DocumentItem` rows carry `VIGENTE` / `MODIFICADO` / `DEROGADO` status and a `supersedes_id` link. Retrieval does not filter on validity status, so deleting chunks is the only thing that stops the assistant citing dead regulations: every path that sets `DEROGADO` calls `vector_store.delete_by_document_id()` (partial derogations use `delete_chunks_by_article()`). Those calls open their own session, so they commit separately from the status update. The FK `ondelete="CASCADE"` on `DocumentChunk` applies only when the `DocumentItem` row itself is deleted. [normative_auditor.py](backend/app/services/normative_auditor.py) and [markdown_converter.py](backend/app/services/markdown_converter.py) detect derogation clauses when PDFs are converted for ingestion.

**Corpus intake is agentic.** An IMAP poller and an M365 webhook feed institutional mail into [triage_service.py](backend/app/services/triage_service.py), which scores relevance with an LLM and proposes metadata; an admin edits and approves before anything is vectorized.

**Everything is dialect-portable.** Production is Neon PostgreSQL 16 + pgvector (1536-d HNSW cosine); tests and local dev run SQLite. This is handled in two places: `VectorType` in [models.py](backend/app/db/models.py) swaps `Vector(1536)` for JSON `Text`, and [vector_store.py](backend/app/services/vector_store.py) falls back from `<=>` operator search to Python cosine distance. New DDL and queries must work on both. Likewise `llm_adapter.get_embeddings()` falls back to deterministic hash-based pseudo-embeddings when no embedding provider is configured, which is what makes the test suite runnable with no API key.

**Redis is optional by design.** [redis_cache.py](backend/app/core/redis_cache.py) uses Upstash when `UPSTASH_REDIS_URL` is set and a thread-safe in-RAM dict otherwise; both paths are tested.

## Conventions

- Backend code, comments, and docstrings are English; all user-facing strings, prompts, and guardrail messages are Spanish.
- Tests must never create relative SQLite files (`sqlite:///tmp_test.sqlite`) — use `:memory:` or `tempfile` with unconditional cleanup. A hygiene test asserts no stray `tmp_test.sqlite` exists.
- The SSE frame vocabulary (`queue`, `queue_ready`, `token`, `citations`, `security_ban`, `: ping`, `[DONE]`) is a cross-layer contract: changing it means changing both `chat.py` and `streamChat()` in [frontend/src/lib/api.ts](frontend/src/lib/api.ts).
- Frontend: no unreferenced components or dead CSS (a test asserts specific orphans stay deleted); all `localStorage` access goes through [storage.ts](frontend/src/lib/storage.ts); floating citation modals render via `createPortal` to `document.body`.
- `backend/data/uploads/` and `backend/data/database.sqlite` are working data, not fixtures — don't treat them as generated output to clean.
