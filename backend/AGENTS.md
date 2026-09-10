# CanIGraduateUD-RAG — Backend AI Agent Operating Manual

Operating guide, architecture invariants, and coding standards for AI agents modifying `backend/`.

---

## 1. Tech Stack
| Component | Technology | Configuration / Invariants |
|---|---|---|
| **Framework** | FastAPI 0.111+, Starlette | Python 3.11-slim, async StreamingResponse, CORS middleware |
| **Relational DB** | PostgreSQL 16 (production) | SQLAlchemy 2.0+, psycopg2-binary 2.9.9, SQLite dev fallback |
| **Connection Pool**| SQLAlchemy `QueuePool` | `size=30`, `overflow=50`, `recycle=1800s`, `pre_ping=True`, `timeout=30s` |
| **Query Cache** | Upstash Redis + RAM Fallback | Layer 1 exact SHA-256 + Layer 2 semantic cosine similarity >= 0.95 |
| **Vector Store** | Neon `pgvector` (HNSW) | 100% Stateless in PostgreSQL `document_chunks` (1536-d, cosine ops), SQLite fallback |
| **LLM Provider** | OpenRouter Multi-Model | Primary `llama-3.1-8b`, Fallbacks `llama-3.3-70b` & `gemini-2.0-flash` |
| **Resilience** | Exponential Backoff & Loops | 3 retries (`1.5^attempt`), transient 429/50x retry, repetition detector |
| **Virtual Queue** | FIFO `VirtualQueueManager` | `STREAM_CONCURRENCY_SEMAPHORE` (150 slots), queue (100 cap, 15s wait) |

---

## 2. Directory Layout & Layer Responsibilities
| Directory | Layer Responsibility | Key Files |
|---|---|---|
| `app/core/` | Cross-cutting infrastructure, configuration & security | `config.py`, `redis_cache.py`, `security_guardrails.py`, `virtual_queue.py` |
| `app/db/` | Database persistence, schema models & connection factory | `models.py` (7 tables), `session.py` (QueuePool & init_db) |
| `app/api/` | HTTP & SSE presentation layer, authentication & routes | `deps.py`, `v1/chat.py`, `v1/admin.py`, `v1/documents.py`, `v1/webhooks.py` |
| `app/services/` | Business logic, RAG pipeline, LLM & vector operations | `rag_service.py`, `llm_adapter.py`, `vector_store.py`, `document_processor.py` |
| `scripts/` | Database migration and maintenance utilities | `migrate_sqlite_to_postgres.py` |
| `tests/` | Automated test suite (unit, integration, concurrency, E2E) | 8 test files, 121 automated tests |

---

## 3. Essential Commands
```bash
# Activate virtual environment
source backend/.venv/bin/activate

# Start development server with auto-reload (run from backend/)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Execute entire test suite (run from project root)
backend/.venv/bin/pytest backend/tests -q

# Execute targeted test module
backend/.venv/bin/pytest backend/tests/test_virtual_queue.py -v

# Simulate database migration (Dry-Run)
backend/.venv/bin/python backend/scripts/migrate_sqlite_to_postgres.py --dry-run

# Execute SQLite to PostgreSQL migration
backend/.venv/bin/python backend/scripts/migrate_sqlite_to_postgres.py --source backend/data/database.sqlite --target "$DATABASE_URL"

# Start production containers
docker compose up -d postgres backend
```

---

## 4. Key Configuration & Environment Variables
| Variable | Default Value | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///data/database.sqlite` | PostgreSQL or SQLite connection string |
| `UPSTASH_REDIS_URL` | `""` | Primary Upstash Redis URL (falls back to RAM cache) |
| `OPENROUTER_MODEL` | `meta-llama/llama-3.1-8b-instruct` | Primary LLM model for RAG generation |
| `OPENROUTER_FALLBACK_MODELS`| `llama-3.3-70b, gemini-2.0-flash` | Ordered fallback models for resilience |
| `STREAM_CONCURRENCY_LIMIT` | `150` | Maximum active concurrent LLM stream permits |
| `QUEUE_CAPACITY` | `100` | Maximum waiting requests in Virtual Queue |
| `QUEUE_MAX_WAIT_SECONDS` | `15.0` | Maximum queue wait timeout before client 503 |
| `SSE_KEEPALIVE_INTERVAL_SECONDS` | `15.0` | Keepalive comment `: ping` emission interval |

---

## 5. SSE Streaming Wire Protocol
| Event Type | Payload Format | Purpose |
|---|---|---|
| `queue` | `data: {"type": "queue", "position": 1, "estimated_seconds": 2}\n\n` | Position in virtual queue when slots busy |
| `queue_ready`| `data: {"type": "queue_ready"}\n\n` | Signal that semaphore permit was claimed |
| `token` | `data: {"type": "token", "content": "chunk"}\n\n` | Incremental answer tokens from LLM |
| `citations` | `data: {"type": "citations", "citations": [...]}\n\n` | Verified normative citations list |
| `: ping` | `: ping\n\n` | Keepalive comment (emitted every 15s) |
| `[DONE]` | `data: [DONE]\n\n` | Stream terminal signal |

---

## 6. Critical Coding Invariants

### A. Database Sessions & Connection Pooling
- **FastAPI Endpoints**: Always inject DB sessions via `Depends(get_db)`. It guarantees session closure via `finally: db.close()`.
- **Background Workers & Generators**: Never pass request-scoped sessions to threads or SSE generators. Instantiate a standalone session:
  ```python
  db = SessionLocal()
  try:
      # execute operations
  finally:
      db.close()
  ```
- **Connection Health**: `pool_pre_ping=True` is mandatory for PostgreSQL to catch terminated sockets before executing queries.

### B. Concurrency & Virtual Queue
- **Semaphore Acquisition**: All streaming requests MUST acquire `STREAM_CONCURRENCY_SEMAPHORE` (150 capacity limit).
- **Guaranteed Permit Release**: Wrap acquired permits in `SemaphoreReleaseGuard`. Unconditional release occurs on stream finish (`[DONE]`), client abort (`GeneratorExit`), exceptions, or garbage collection.
- **Cascade Wakeup**: Every permit release MUST invoke `virtual_queue.notify_available()` to unblock waiting tickets immediately.

### C. Zero-Token Pre-Flight Security Gates
Before touching LLM tokens or vector embeddings, all incoming queries MUST traverse 4 zero-token security gates:
1. **Gate 1 — 24h Ban Check**: Verify client IP, subnet (`/24` or `/64`), MAC address, and device ID against `strike_manager`.
2. **Gate 2 — Rate Limiter**: Enforce sliding window (10 requests/min). Exceeding returns HTTP 429.
3. **Gate 3 — Attack & Abuse Gate**: Scan regex patterns for prompt injection, system prompt extraction, jailbreaks, and non-academic queries. Log strikes (3 strikes = 24h ban).
4. **Gate 4 — Benign Greeting Gate**: Direct orientation for "hola" / "quién eres" without consuming LLM tokens.
5. **Gate 5 — Hybrid Cache**: Check Layer 1 (exact normalized SHA-256) and Layer 2 (semantic cosine similarity >= 0.95).

### D. Testing Invariants & Artifact Hygiene
- **Zero Orphan SQLite Files**: NEVER configure relative SQLite file paths in tests (e.g., `sqlite:///tmp_test.sqlite`). Use `sqlite:///:memory:` or `tempfile.NamedTemporaryFile` with unconditional file removal in `finally:`.
- **State Reset Fixtures**: Concurrency and queue tests must use autouse fixtures to restore semaphore permits and reset queue state.

---

## 7. Testing Standard (131 Tests)
| Test Module | Tests | Verified Functional Scope |
|---|---|---|
| `test_redis_cache.py` | 34 | Dual-layer cache, SHA-256 exact match, semantic cosine, RAM fallback, TTL |
| `test_openrouter_resilience.py` | 30 | Fallbacks, exponential backoff, transient vs permanent 4xx, repetition loops |
| `test_postgres_session.py` | 15 | QueuePool parameters, dialect-agnostic DDL, CRUD across all 6 models |
| `test_security_guardrails.py` | 15 | Prompt injection, 0-token abuse gates, 3-strikes rule, 24h ban, subnet IP |
| `test_concurrency_and_keepalive.py`| 11 | Semaphore 150 limit, keepalive `: ping`, unconditional permit release |
| `test_virtual_queue.py` | 10 | FIFO queue order, capacity saturation (503), cascading ticket wake |
| `test_pdf_deduplication.py` | 6 | Bold OCR deduplication, Spanish diacritics, citation deduplication |
| `test_pgvector_store.py` | 5 | HNSW cosine similarity, VectorType, filtering, cascade delete |
| `e2e/test_derogation_e2e.py` | 1 | Granular article and total document derogation lifecycle |

All 131 tests MUST pass: `backend/.venv/bin/pytest backend/tests -q`.

---

## 8. Modular Documentation Pointers
Detailed specifications and deep architecture are organized in `backend/docs/`:
- [`backend/docs/architecture.md`](docs/architecture.md): System architecture diagram (Mermaid), SSE streaming protocol, 4 zero-token gates, 3-strikes penalty system, Virtual Queue state machine, and OpenRouter resilience.
- [`backend/docs/database_and_caching.md`](docs/database_and_caching.md): PostgreSQL schema for all 6 tables, QueuePool parameters, migration script guide, hybrid caching (L1/L2/RAM), and ChromaDB derogation filtering.
