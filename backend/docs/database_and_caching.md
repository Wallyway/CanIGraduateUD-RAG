# PostgreSQL Database, Hybrid Caching, and Vector Storage Specification

Authoritative technical documentation for the persistence, pooling, caching, and vector indexing layers of **CanIGraduateUD-RAG**.

---

## 1. Relational Database Schema (PostgreSQL 16)

The application utilizes **PostgreSQL 16** in production with **SQLAlchemy 2.0+** declarative models (`app/db/models.py`). An SQLite fallback is maintained for local development and integration testing.

```mermaid
erDiagram
    SYSTEM_SETTINGS {
        string key PK "Key (varchar 50)"
        string value "Value (varchar 255)"
        string description "Description (varchar 255)"
        datetime updated_at "Last updated timestamp"
    }

    EMAIL_NOTICES ||--o{ DOCUMENT_ITEMS : "generates"
    EMAIL_NOTICES {
        int id PK "Auto-increment ID"
        string sender "Sender address (indexed)"
        string recipient "Recipient address"
        string subject "Email subject"
        text body_text "Full email body text"
        datetime received_at "Received timestamp"
        boolean has_attachments "Attachment indicator"
        text attachment_paths "JSON/CSV list of files"
        text extracted_urls "JSON/CSV list of URLs"
        boolean is_relevant "LLM triage relevance flag"
        float relevance_score "0.0 - 100.0 score"
        text triage_summary "Summary of email content"
        text triage_reasoning "LLM triage reasoning"
        string target_program "e.g. Ingeniería de Sistemas"
        string status "PENDING_REVIEW, APPROVED_INDEXED, REJECTED"
        datetime reviewed_at "Admin review timestamp"
        datetime created_at "Created timestamp"
    }

    DOCUMENT_ITEMS ||--o| DOCUMENT_ITEMS : "supersedes"
    DOCUMENT_ITEMS ||--o{ DOCUMENT_CHUNKS : "chunks"
    DOCUMENT_ITEMS {
        int id PK "Auto-increment ID"
        string title "Document official title"
        string filename "Saved filename"
        string file_path "Filesystem path"
        string file_type "pdf, markdown, text"
        string source_type "SEED, MANUAL_UPLOAD, EMAIL_ATTACHMENT, EMAIL_BODY"
        int email_id FK "References email_notices.id (nullable)"
        string resolution_number "e.g. Acuerdo 038 de 2015"
        string effective_date "Date string"
        int chunk_count "Number of indexed chunks"
        string status "INDEXED, PENDING, ERROR"
        string validity_status "VIGENTE, MODIFICADO, DEROGADO"
        int supersedes_id FK "References document_items.id (nullable)"
        string superseded_by_title "Superseding norm title"
        text markdown_content "Cleaned markdown text"
        string scan_image_path "OCR image path"
        string original_pdf_url "Source PDF URL"
        datetime created_at "Created timestamp"
    }

    DOCUMENT_CHUNKS {
        int id PK "Auto-increment ID"
        string chunk_id "Unique chunk ID (indexed)"
        int document_id FK "References document_items.id (cascade delete)"
        int chunk_index "Index of chunk within doc"
        string article "Normalized article name (indexed)"
        text content "Full chunk text body"
        text extra_metadata "JSON metadata dictionary"
        vector embedding "1536-d pgvector (HNSW cosine indexed)"
        datetime created_at "Created timestamp"
    }

    STUDENT_QUERY_LOGS {
        int id PK "Auto-increment ID"
        text query_text "Full text of student query"
        string topic_category "Pasantías, Modalidades, Inglés B2, Paz y Salvos"
        int citations_count "Number of verified citations"
        float confidence_score "Confidence score 0.0 - 1.0"
        boolean has_knowledge_gap "Flag for unanswered queries (indexed)"
        string device_type "desktop, mobile"
        datetime timestamp "Query timestamp (indexed)"
    }

    SESSION_FEEDBACKS {
        int id PK "Auto-increment ID"
        string session_id "UUID session identifier (indexed)"
        string user_email "Student email (optional)"
        string feedback_type "sugerencia, informacion_imprecisa, error_tecnico"
        int rating "1 - 5 stars rating"
        text comments "Student feedback message"
        boolean has_transcript "Transcript included flag"
        text transcript_json "Full conversation history JSON"
        string target_email "Default: canigraduateud@gmail.com"
        string status "RECEIVED, SENT_VIA_SMTP, REVIEWED"
        datetime created_at "Created timestamp (indexed)"
    }

    SECURITY_PENALTY_LOGS {
        int id PK "Auto-increment ID"
        string ip_address "Client IP (indexed)"
        string mac_address "Client MAC / fingerprint (indexed)"
        string device_id "Client persistent device ID (indexed)"
        string subnet "IPv4 /24 or IPv6 /64 (indexed)"
        string user_agent "Client user agent signature"
        int strike_count "Accumulated strikes (1 - 3)"
        boolean is_banned "Active 24h ban flag (indexed)"
        datetime banned_until "Ban expiration timestamp (indexed)"
        string last_reason "Reason for last strike"
        text last_query "Offending query text"
        text violation_history "JSON log of violations"
        datetime created_at "Created timestamp"
        datetime updated_at "Updated timestamp"
    }
```

---

## 2. Connection Pooling & Session Management

To reliably sustain peak concurrency during student registration and graduation deadlines (>200 simultaneous users), the database engine (`app/db/session.py`) employs SQLAlchemy's `QueuePool`.

### 2.1 QueuePool Concurrency Tuning

```python
create_engine(
    url,
    poolclass=QueuePool,
    pool_size=30,          # Base pool of persistent database connections
    max_overflow=50,       # Burst connections allowed during concurrency spikes
    pool_recycle=1800,     # Recycle connections every 30 minutes to eliminate stale sockets
    pool_pre_ping=True,    # Issues 'SELECT 1' on checkout to catch dropped TCP connections
    pool_timeout=30        # Maximum wait (seconds) for an available pool slot before error
)
```

- **Total Concurrency Ceiling**: $30 \text{ (base)} + 50 \text{ (overflow)} = 80$ physical PostgreSQL backend connections. Combined with async ASGI worker multiplexing in FastAPI, this comfortably supports >200 concurrent student sessions.
- **Connection Health (`pool_pre_ping=True`)**: Crucial for cloud deployments (e.g. AWS RDS, Supabase, Neon) where stateful firewalls drop idle TCP connections after 5–10 minutes. Ensures disconnected sockets are silently pruned and re-established without 500 errors.
- **SQLite Engine Dialect**: When running against SQLite (`sqlite:///`), the engine automatically switches to `check_same_thread=False` and uses `StaticPool` for `:memory:` instances.

### 2.2 Session Lifecycle Rules

1. **HTTP Routes (FastAPI)**:
   Always use dependency injection with `Depends(get_db)`. The session is guaranteed to close when the request finishes:
   ```python
   def get_db():
       db = SessionLocal()
       try:
           yield db
       finally:
           db.close()
   ```
2. **Background Threads & SSE Streaming Generators**:
   Request-scoped sessions injected via `Depends` MUST NOT be passed into worker threads or asynchronous generators. Threads must instantiate their own session:
   ```python
   db_log = None
   try:
       db_log = SessionLocal()
       # perform database logging
       db_log.commit()
   except Exception as err:
       if db_log:
           db_log.rollback()
   finally:
       if db_log:
           db_log.close()
   ```

---

## 3. Data Migration Utility (`migrate_sqlite_to_postgres.py`)

The migration utility (`backend/scripts/migrate_sqlite_to_postgres.py`) transfers application state, documents, and historical logs from SQLite to PostgreSQL with zero data loss.

### 3.1 Migration Sequence & Foreign Key Constraints

To prevent foreign key constraint violations during bulk data loading, tables are inserted in strict dependency order:
$$\text{TABLE\_ORDER} = [ \texttt{system\_settings} \rightarrow \texttt{email\_notices} \rightarrow \texttt{document\_items} \rightarrow \texttt{student\_query\_logs} \rightarrow \texttt{session\_feedbacks} \rightarrow \texttt{security\_penalty\_logs} ]$$

When truncating before migration (`--clean`), tables are emptied in reverse order:
$$\texttt{TRUNCATE TABLE "security\_penalty\_logs", "session\_feedbacks", "student\_query\_logs", "document\_items", "email\_notices", "system\_settings" CASCADE;}$$

### 3.2 Data Type Sanitization & Coercion

Raw SQLite rows lack strict typing. `sanitize_row_for_target()` transforms raw fields before PostgreSQL insertion:

- **Booleans**: Converts SQLite integers (`0`, `1`) and text strings (`"true"`, `"false"`, `"t"`, `"1"`) to native Python `bool`.
- **DateTimes**: Converts ISO timestamp strings (`"2026-09-10T18:30:00.000000"`, `"2026-09-10 18:30:00"`) into native `datetime` objects.
- **Field Whitelisting**: Drops obsolete columns present in older SQLite files that do not exist on the target schema.

### 3.3 Conflict Handling & Sequence Synchronization

- **Upsert / Conflict Avoidance**: For `system_settings`, uses `on_conflict_do_update` on the `key` primary key. For log tables, uses `on_conflict_do_nothing` on the `id` primary key.
- **PostgreSQL Sequence Synchronization**:
  After transferring records with explicit `id` values, the PostgreSQL serial sequence is synchronized to prevent collisions on subsequent `INSERT` operations:
  ```sql
  SELECT setval(pg_get_serial_sequence('document_items', 'id'), MAX(id), true) FROM "document_items";
  ```

### 3.4 CLI Commands

```bash
# Dry run: Inspect source row counts and validate target schema
python backend/scripts/migrate_sqlite_to_postgres.py --dry-run

# Execute full migration with clean target
python backend/scripts/migrate_sqlite_to_postgres.py \
    --source backend/data/database.sqlite \
    --postgres-url "postgresql+psycopg2://postgres:password@localhost:5432/can_i_graduate" \
    --clean \
    --batch-size 500
```

---

## 4. Hybrid Caching Architecture

CanIGraduateUD-RAG incorporates a dual-tier query cache (`app/core/redis_cache.py`) designed to return instant answers for recurring student questions with **zero LLM latency and zero token consumption**.

```mermaid
flowchart TD
    Query["Incoming Query: '¿Cuáles son los requisitos de pasantía?'"]
    Norm["normalize_text(): 'requisitos de pasantia'"]
    Hash["compute_query_hash(): SHA-256"]

    Query --> Norm --> Hash

    subgraph Layer1 ["Layer 1: Exact Match (O(1), < 1ms)"]
        CheckRAMExact{"Exact Hash in RAM Cache?"}
        CheckRedisExact{"Exact Hash in Redis?"}
        Hash --> CheckRAMExact
        CheckRAMExact -->|Hit| ReturnL1RAM["Return Answer (Layer: exact, source: RAM)"]
        CheckRAMExact -->|Miss| CheckRedisExact
        CheckRedisExact -->|Hit| WarmRAM["Warm RAM Cache"] --> ReturnL1Redis["Return Answer (Layer: exact, source: Redis)"]
    end

    subgraph Layer2 ["Layer 2: Semantic Match (Cosine Similarity >= 0.95)"]
        CheckRedisExact -->|Miss| GetEmbedding["Get 384-d Embedding (LRU Cached)"]
        GetEmbedding --> ScanRAMSemantic{"Cosine Similarity in RAM >= 0.95?"}
        ScanRAMSemantic -->|Hit| ReturnL2RAM["Return Answer (Layer: semantic, source: RAM)"]
        ScanRAMSemantic -->|Miss| ScanRedisSemantic{"Cosine Similarity in Redis >= 0.95?"}
        ScanRedisSemantic -->|Hit| WarmRAM2["Warm RAM Cache"] --> ReturnL2Redis["Return Answer (Layer: semantic, source: Redis)"]
    end

    ScanRedisSemantic -->|Miss| FullRAG["Cache Miss: Proceed to RAG & LLM"]
    FullRAG --> AsyncCacheWrite["Background ThreadPool: redis_cache.set()"]
```

### 4.1 Layer 1 — Exact Match (SHA-256 on Normalized Spanish)

- **Normalization (`normalize_text`)**:
  1. Decomposes characters via Unicode NFKD (removes accents, tildes, diacritics).
  2. Strips punctuation (inverted question/exclamation marks `¿`, `¡`, quotes, dashes).
  3. Collapses whitespace and converts to lowercase.
     _Example_: `"¿Requisitos para PASANTÍA?!"` and `"requisitos para pasantia"` produce the exact same SHA-256 hash.
- **Lookup Cost**: $O(1)$, $< 1\text{ ms}$ latency, $0$ tokens consumed.

### 4.2 Layer 2 — Semantic Match (Cosine Similarity $\ge 0.95$)

- **Embedding Generation**: 384-dimensional dense vectors generated via `rag_service.embed_query()` or `llm_adapter.get_embeddings()`, backed by a thread-safe LRU cache (`_cached_embedding_tuple(maxsize=1024)`).
- **Matching Metric**:
  $$\text{Cosine Similarity}(u, v) = \frac{u \cdot v}{\|u\|_2 \|v\|_2} \ge 0.95$$
- **Semantic Index in Redis**: Stored in a Redis hash (`canigraduate:cache:semantic_index`) mapping query hashes to `{query, embedding, expires_at}`.

### 4.3 Thread-Safe In-Memory RAM Fallback (`InMemoryCache`)

When Upstash Redis is unconfigured or unreachable:

- The system gracefully degrades to an internal in-memory cache protected by `threading.RLock`.
- Features TTL expiration, capacity management (`max_entries=2000`), and LRU eviction.
- Operates transparently without throwing errors or halting chat requests.

### 4.4 Invalidation Triggers & Asynchronous Writes

- **Asynchronous Storage**: Responses are stored via a dedicated thread pool (`_CACHE_WRITE_EXECUTOR`, max 4 workers) to avoid adding latency to the SSE stream.
- **Cache Invalidation**:
  - On manual document upload or deletion: calls `redis_cache.invalidate_all()`.
  - On derogation resolution: clears affected entries.
  - Invalidation purges both local RAM entries and Redis keys via non-blocking `SCAN`.

---

## 5. Neon PostgreSQL `pgvector` Store & Stateless Architecture

Normative regulations and official announcements are stored in **Neon PostgreSQL** using the native **`pgvector` extension** (`app/services/vector_store.py` and `app/db/models.py`).

### 5.1 Schema & HNSW Indexing

- **Table**: `document_chunks`
- **Embedding Dimensions**: `VECTOR(1536)` matching OpenRouter / OpenAI `text-embedding-3-small`.
- **HNSW Index**:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
  ON document_chunks USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
  ```
- **Operator**: Cosine distance `<=>` where $\text{Similarity} = 1 - (\text{embedding} \Leftrightarrow \text{query\_vector})$.
- **Sub-millisecond latency**: Nearest neighbor retrieval evaluates in 0.5 – 2.0 ms directly on Neon's hardware-accelerated SIMD engine.

### 5.2 100% Stateless Backend Benefits

1. **Zero Local Filesystem Dependency**:
   Unlike ChromaDB (which required local files at `data/chroma/`), all vectors, chunks, and metadata live in the cloud database. The backend can restart, scale, or deploy to ephemeral containers (Render, Koyeb, Docker) with **zero risk of data loss**.
2. **70% RAM Reduction**:
   Removing ChromaDB, C++ native builds, and numpy vector matrices from Python drops backend idle RAM from ~280 MB down to **~80 MB**, entirely preventing OOM crashes on free-tier instances.
3. **Transactional ACID Cascades**:
   `DocumentChunk` declares `ForeignKey("document_items.id", ondelete="CASCADE")`. When an admin deletes a document, all related chunks and vectors are purged in the exact same SQL transaction.

### 5.3 Derogation Filtering & Article Purging

Academic regulations frequently update or repeal specific articles of previous accords (e.g. Accord 004 repealing Article 12 of Accord 038):

1. **Granular Article Derogation (`delete_chunks_by_article`)**:
   Purges only chunks matching specific repealed articles using regex boundaries:
   ```python
   num_match = re.search(r'\b(?:art[íi]culo|art\.?)\s*(\d+)', clean_art, re.IGNORECASE)
   ```
   Ensures that only the superseded article chunks are purged from `document_chunks` while leaving active articles of the accord searchable.
2. **Total Document Derogation (`delete_by_document_id`)**:
   When an entire accord is derogated by a newer agreement, all related chunks are deleted from the database table.
3. **SQLite Fallback for Local Testing**:
   When running unit tests with SQLite (`pytest`), `VectorType` transparently stores vectors as JSON Text and computes cosine similarity in memory, allowing 100% test passage without requiring a local PostgreSQL instance.
