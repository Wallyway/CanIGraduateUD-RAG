import time
import math
try:
    import pytest
except ImportError:
    pytest = None
from unittest.mock import MagicMock, patch
from concurrent.futures import ThreadPoolExecutor

from app.core.redis_cache import (
    HybridRedisCache,
    InMemoryCache,
    normalize_text,
    compute_query_hash,
    cosine_similarity,
    redis_cache
)


# ==============================================================================
# 1. TEST NORMALIZATION & LAYER 1 EXACT MATCH (ACCENTS, CASE, WHITESPACE)
# ==============================================================================

def test_text_normalization():
    """Verifies that accents, casing, whitespace, and punctuation are normalized."""
    q_base = "cuales son los requisitos de pasantia"
    
    variations = [
        "¿Cuáles son los requisitos de pasantía?",
        "  CUÁLES   SON   LOS   REQUISITOS DE PASANTÍA?!  ",
        "cuales son los requisitos de pasantia",
        "¿Cuáles  son   los   requisitos   de   pasantía? \n\t",
        "¡CUALES SON LOS REQUISITOS DE PASANTÍA!",
        "cuales son los requisitos de pasantia..."
    ]
    
    for v in variations:
        normalized = normalize_text(v)
        assert normalized == q_base, f"Failed normalization for: {v} -> got: '{normalized}'"
        assert compute_query_hash(v) == compute_query_hash(q_base)


def test_layer1_exact_match_variants():
    """Verifies that any formatting/accent/whitespace variation hits Layer 1 exact match."""
    cache = HybridRedisCache(redis_url="", default_ttl=60)
    
    query = "¿Requisitos para Iniciar PASANTÍA de Grado en Sistemas?"
    answer = "Para iniciar pasantía requieres tener el 80% de créditos aprobados y promedio >= 3.2."
    citations = [{"title": "Acuerdo 038 de 2015", "resolution": "Art. 12"}]
    topic = "Pasantías"

    success = cache.set(query=query, answer=answer, citations=citations, topic=topic)
    assert success is True

    # Test exact variants
    variants = [
        "¿Requisitos para Iniciar PASANTÍA de Grado en Sistemas?",
        "requisitos para iniciar pasantia de grado en sistemas",
        "  REQUISITOS   PARA   INICIAR   PASANTIA DE GRADO EN SISTEMAS?! ",
        "¿requisitos para iniciar pasantía de grado en sistemas?"
    ]

    for v in variants:
        res = cache.get(v)
        assert res is not None, f"Expected cache hit for variation: {v}"
        assert res["cache_hit"] is True
        assert res["cache_layer"] == "exact"
        assert res["similarity"] == 1.0
        assert res["answer"] == answer
        assert res["citations"] == citations
        assert res["topic"] == topic


# ==============================================================================
# 2. TEST LAYER 2 SEMANTIC MATCH (COSINE SIMILARITY >= 0.95)
# ==============================================================================

def test_cosine_similarity_computation():
    """Verifies mathematical correctness of cosine similarity."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert math.isclose(cosine_similarity(v1, v2), 1.0)

    v_ortho = [0.0, 1.0, 0.0]
    assert math.isclose(cosine_similarity(v1, v_ortho), 0.0)

    # Empty or zero vectors
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_semantic_match_above_threshold():
    """Verifies semantic cache hit when cosine similarity >= 0.95."""
    cache = HybridRedisCache(redis_url="", default_ttl=60, semantic_threshold=0.95)

    # Unit vector 1
    dim = 64
    v1 = [1.0 / math.sqrt(dim)] * dim

    # Store base query with v1
    cache.set(
        query="fechas de entrega de monografia",
        answer="La fecha límite de entrega de monografía es el 15 de noviembre.",
        citations=[{"title": "Calendario Académico 2026"}],
        topic="Modalidades",
        embedding=v1
    )

    # Create v2 very close to v1 (similarity ~ 0.98)
    v2 = list(v1)
    v2[0] += 0.05
    norm2 = math.sqrt(sum(x * x for x in v2))
    v2 = [x / norm2 for x in v2]

    sim = cosine_similarity(v1, v2)
    assert sim >= 0.95, f"Test vector similarity {sim} should be >= 0.95"

    # Query with completely different text (to miss Layer 1) but passing v2 embedding
    res = cache.get("plazo maximo para radicar informe monografia", query_embedding=v2)
    assert res is not None, "Expected semantic cache hit"
    assert res["cache_hit"] is True
    assert res["cache_layer"] == "semantic"
    assert res["similarity"] >= 0.95
    assert "15 de noviembre" in res["answer"]


# ==============================================================================
# 3. TEST REJECTION OF DISSIMILAR / OFF-TOPIC QUERIES (< 0.95)
# ==============================================================================

def test_rejection_below_threshold():
    """Verifies semantic cache rejects queries with similarity < 0.95."""
    cache = HybridRedisCache(redis_url="", default_ttl=60, semantic_threshold=0.95)

    dim = 64
    v1 = [1.0 / math.sqrt(dim)] * dim

    cache.set(
        query="requisitos de pasantia",
        answer="Requisitos de pasantía...",
        citations=[],
        topic="Pasantías",
        embedding=v1
    )

    # Orthogonal or distant vector
    v_diff = [0.0] * dim
    v_diff[0] = 1.0  # similarity ~ 1/sqrt(64) = 0.125 < 0.95

    sim = cosine_similarity(v1, v_diff)
    assert sim < 0.95

    res = cache.get("como solicitar certificado de notas", query_embedding=v_diff)
    assert res is None, "Should miss cache when similarity < 0.95"


def test_empty_and_whitespace_queries():
    """Verifies that empty, whitespace, or invalid queries return None without errors."""
    cache = HybridRedisCache(redis_url="", default_ttl=60)
    assert cache.get("") is None
    assert cache.get("   ") is None
    assert cache.set("", "answer", [], "topic") is False
    assert cache.set("query", "", [], "topic") is False


# ==============================================================================
# 4. TEST RAM FALLBACK WHEN REDIS IS ABSENT OR FAILS
# ==============================================================================

def test_ram_fallback_unconfigured_redis():
    """Verifies cache operates 100% in RAM when Redis URL is unconfigured."""
    cache = HybridRedisCache(redis_url="")
    assert cache.is_redis_available() is False
    assert cache.redis_enabled is False

    success = cache.set("test query", "test answer", [{"title": "Doc 1"}], "General")
    assert success is True

    res = cache.get("test query")
    assert res is not None
    assert res["answer"] == "test answer"
    assert res["citations"] == [{"title": "Doc 1"}]


def test_ram_fallback_invalid_redis_url():
    """Verifies graceful fallback when Redis URL is unreachable."""
    # Attempt connection to non-existent Redis port
    cache = HybridRedisCache(redis_url="redis://127.0.0.1:59998/0")
    assert cache.is_redis_available() is False
    assert cache.redis_enabled is False

    # Still works in RAM without throwing exceptions
    cache.set("fallback query", "fallback answer", [], "General")
    res = cache.get("fallback query")
    assert res is not None
    assert res["answer"] == "fallback answer"


def test_ram_fallback_on_redis_runtime_exception():
    """Verifies that runtime exceptions from Redis (e.g. quota limit, timeout) fall back to RAM."""
    cache = HybridRedisCache(redis_url="")
    cache.redis_enabled = True
    mock_client = MagicMock()
    # Mock Redis raising ConnectionError or ResponseError
    mock_client.get.side_effect = Exception("ERR max daily request limit exceeded (Upstash Quota)")
    mock_client.setex.side_effect = Exception("Redis connection timeout")
    cache.client = mock_client

    # Write: should not raise exception and should succeed in RAM
    success = cache.set("resilience query", "resilience answer", [], "Resilience")
    assert success is True

    # Read: should catch Redis error and successfully return from RAM
    res = cache.get("resilience query")
    assert res is not None
    assert res["answer"] == "resilience answer"


# ==============================================================================
# 5. TEST TTL EXPIRATION
# ==============================================================================

def test_ttl_expiration():
    """Verifies that entries expire after their TTL has elapsed."""
    cache = HybridRedisCache(redis_url="", default_ttl=1)

    # Set with 1-second TTL
    cache.set(
        query="temporal query",
        answer="temporal answer",
        citations=[],
        topic="General",
        ttl=1
    )

    # Immediately available
    res = cache.get("temporal query")
    assert res is not None
    assert res["answer"] == "temporal answer"

    # Wait for TTL to expire
    time.sleep(1.15)

    # Now expired
    expired_res = cache.get("temporal query")
    assert expired_res is None, "Cached item should have expired after TTL"


# ==============================================================================
# 6. TEST INVALIDATION UTILITIES
# ==============================================================================

def test_invalidate_all():
    """Verifies that invalidate_all flushes all entries from cache."""
    cache = HybridRedisCache(redis_url="", default_ttl=60)

    cache.set("q1", "a1", [], "Topic 1")
    cache.set("q2", "a2", [], "Topic 2")
    cache.set("q3", "a3", [], "Topic 3")

    assert cache.get("q1") is not None
    assert cache.get("q2") is not None
    assert cache.get("q3") is not None

    cache.invalidate_all()

    assert cache.get("q1") is None
    assert cache.get("q2") is None
    assert cache.get("q3") is None


def test_delete_single_key():
    """Verifies that delete removes only the specified query."""
    cache = HybridRedisCache(redis_url="", default_ttl=60)

    cache.set("to_delete", "a1", [], "Topic 1")
    cache.set("to_keep", "a2", [], "Topic 2")

    cache.delete("to_delete")

    assert cache.get("to_delete") is None
    assert cache.get("to_keep") is not None


# ==============================================================================
# 7. TEST CONCURRENCY & THREAD SAFETY
# ==============================================================================

def test_thread_safety_concurrent_access():
    """Verifies thread-safety under heavy concurrent reads and writes."""
    cache = HybridRedisCache(redis_url="", default_ttl=60)

    def worker(worker_id: int):
        for i in range(25):
            q = f"concurrent query {worker_id}_{i}"
            a = f"concurrent answer {worker_id}_{i}"
            cache.set(q, a, [], "Concurrency")
            res = cache.get(q)
            assert res is not None
            assert res["answer"] == a

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, w) for w in range(8)]
        for f in futures:
            f.result()

    stats = cache.get_stats()
    assert stats["writes"] == 200
    assert stats["exact_hits"] == 200


# ==============================================================================
# 8. TEST INTEGRATION WITH CHAT STREAM ENDPOINT (HTTP & SSE HEADERS)
# ==============================================================================

def test_chat_stream_cache_hit_integration():
    """
    Simulates chat stream execution to verify:
    1. Cache miss sets X-Cache-Hit: false.
    2. Cache hit returns X-Cache-Hit: true, 0 OpenRouter calls, and correct SSE format.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    from app.db.session import init_db
    init_db()

    # Reset global cache for clean test
    redis_cache.invalidate_all()

    client = TestClient(app)

    test_query = "¿Cuáles son los requisitos de pasantía institucional?"

    # First request: Cache Miss -> standard stream
    def parse_sse_text(raw_sse: str) -> str:
        import json
        tokens = []
        for line in raw_sse.splitlines():
            if line.startswith("data: ") and not line.endswith("[DONE]"):
                data = json.loads(line[6:])
                if data.get("type") == "token":
                    tokens.append(data.get("content", ""))
        return "".join(tokens)

    from app.services.rag_service import rag_service

    mock_events = [
        {"type": "token", "content": "Para iniciar pasantía "},
        {"type": "token", "content": "se requiere 80% de créditos aprobados."},
        {"type": "citations", "citations": [{"title": "Acuerdo 038 de 2015", "resolution": "Art. 12"}]}
    ]

    # First request: Cache Miss -> calls rag_service.answer_stream
    with patch.object(rag_service, "answer_stream", return_value=mock_events), \
         patch.object(rag_service, "embed_query", return_value=[0.1] * 384):
        resp1 = client.post(
            "/api/v1/chat/stream",
            json={"query": test_query, "history": []},
            headers={"X-Forwarded-For": "192.168.1.150"}
        )
        assert resp1.status_code == 200
        assert resp1.headers.get("X-Cache-Hit") == "false"
        assert "data: " in resp1.text
        assert "[DONE]" in resp1.text
        tokens1 = parse_sse_text(resp1.text)
        assert "80% de créditos aprobados." in tokens1

    # Wait briefly for the asynchronous background thread to commit to cache
    time.sleep(0.5)

    # Second request with identical query: Cache Hit! (Does NOT call OpenRouter / answer_stream)
    resp2 = client.post(
        "/api/v1/chat/stream",
        json={"query": test_query, "history": []},
        headers={"X-Forwarded-For": "192.168.1.151"}
    )
    assert resp2.status_code == 200
    assert resp2.headers.get("X-Cache-Hit") == "true"
    tokens2 = parse_sse_text(resp2.text)
    assert tokens2 == tokens1
    assert "Acuerdo 038 de 2015" in resp2.text
    assert "[DONE]" in resp2.text

    # Third request with case and accents variation: Layer 1 Exact Match Hit!
    resp3 = client.post(
        "/api/v1/chat/stream",
        json={"query": "  cuales son los requisitos de pasantia institucional?!  ", "history": []},
        headers={"X-Forwarded-For": "192.168.1.152"}
    )
    assert resp3.status_code == 200
    assert resp3.headers.get("X-Cache-Hit") == "true"
    tokens3 = parse_sse_text(resp3.text)
    assert tokens3 == tokens1
    assert "Acuerdo 038 de 2015" in resp3.text
    assert "[DONE]" in resp3.text


# ==============================================================================
# 9. TEST UNICODE SMART QUOTES & MOBILE PUNCTUATION NORMALIZATION
# ==============================================================================

def test_unicode_smart_quotes_and_symbols_normalization():
    """
    Verifies that mobile smart quotes (“...”, ‘...’), French/Spanish guillemets («...»),
    and em-dashes (—) normalize identically to standard plain text queries.
    """
    base = "requisitos de pasantia institucional"
    smart_variants = [
        "“requisitos de pasantía institucional”",
        "‘requisitos de pasantía institucional’",
        "«requisitos de pasantía institucional»",
        "—requisitos de pasantía institucional—",
        "¿«requisitos de pasantía institucional»?!"
    ]

    for v in smart_variants:
        norm = normalize_text(v)
        assert norm == base, f"Smart punctuation normalization failed for '{v}' -> '{norm}'"
        assert compute_query_hash(v) == compute_query_hash(base)


# ==============================================================================
# 10. TEST FUNCTIONAL REDIS OPERATIONS WITH MOCK REDIS CLIENT
# ==============================================================================

def test_redis_operations_mocked():
    """
    Verifies full end-to-end cache interactions when Redis is active:
    - Layer 1 exact match via Redis and RAM cache warming
    - Layer 2 semantic match via Redis semantic index
    - Invalidation via Redis delete & scan_iter
    """
    import json

    cache = HybridRedisCache(redis_url="redis://localhost:6379/0", default_ttl=3600)
    cache.redis_enabled = True

    mock_client = MagicMock()
    redis_store = {}
    redis_hash = {}

    def mock_setex(name, ttl, value):
        redis_store[name] = value

    def mock_get(name):
        return redis_store.get(name)

    def mock_hset(name, key, value):
        redis_hash[key] = value

    def mock_hgetall(name):
        return dict(redis_hash)

    def mock_hdel(name, *keys):
        for k in keys:
            redis_hash.pop(k, None)

    def mock_delete(*keys):
        for k in keys:
            redis_store.pop(k, None)

    def mock_scan_iter(pattern, count=100):
        return [k for k in list(redis_store.keys()) if k.startswith("canigraduate:cache:")]

    mock_client.setex.side_effect = mock_setex
    mock_client.get.side_effect = mock_get
    mock_client.hset.side_effect = mock_hset
    mock_client.hgetall.side_effect = mock_hgetall
    mock_client.hdel.side_effect = mock_hdel
    mock_client.delete.side_effect = mock_delete
    mock_client.scan_iter.side_effect = mock_scan_iter
    mock_client.ping.return_value = True
    cache.client = mock_client

    test_emb = [0.1] * 64

    # 1. Set entry
    success = cache.set(
        query="como inscribir materias",
        answer="A través del sistema Cóndor en las fechas programadas.",
        citations=[{"title": "Calendario Académico"}],
        topic="Plan de Estudios",
        embedding=test_emb,
        ttl=1800
    )
    assert success is True
    assert mock_client.setex.called
    assert mock_client.hset.called

    # 2. Layer 1 hit via Redis: clear RAM cache first to force Redis lookup
    cache.ram_cache.invalidate_all()
    assert cache.ram_cache.size() == 0

    hit = cache.get("como inscribir materias")
    assert hit is not None
    assert hit["cache_hit"] is True
    assert hit["cache_layer"] == "exact"
    assert "sistema Cóndor" in hit["answer"]
    # Verify RAM was warmed
    assert cache.ram_cache.size() == 1

    # 3. Layer 2 semantic hit via Redis: clear RAM, test near vector
    cache.ram_cache.invalidate_all()
    near_emb = [0.1001] * 64
    sem_hit = cache.get("donde inscribo mis materias", query_embedding=near_emb)
    assert sem_hit is not None
    assert sem_hit["cache_hit"] is True
    assert sem_hit["cache_layer"] == "semantic"
    assert "sistema Cóndor" in sem_hit["answer"]

    # 4. Invalidation
    cache.invalidate_all()
    assert cache.ram_cache.size() == 0
    assert mock_client.delete.called


# ==============================================================================
# 11. TEST CLIENT DISCONNECTION / GENERATOR-EXIT RESILIENCE IN CHAT STREAM
# ==============================================================================

def test_client_generator_exit_resilience():
    """
    Verifies that early generator termination (client closes browser tab/disconnects)
    does NOT trigger 'RuntimeError: generator ignored GeneratorExit'.
    """
    from app.api.v1.chat import stream_chat_response, ChatRequest
    from starlette.requests import Request

    # Setup mock request
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"x-forwarded-for", b"10.0.0.99"), (b"user-agent", b"pytest-test")],
        "path": "/api/v1/chat/stream"
    }
    mock_req = Request(scope)
    mock_payload = ChatRequest(query="hola que tal", history=[])
    mock_db = MagicMock()

    # Call streaming endpoint
    response = stream_chat_response(request=mock_req, payload=mock_payload, db=mock_db)
    gen = response.body_iterator

    # Consume first item and simulate client disconnect by closing generator early
    if hasattr(gen, "__anext__"):
        import asyncio
        first_chunk = asyncio.run(gen.__anext__())
        assert first_chunk is not None
        try:
            asyncio.run(gen.aclose())
        except RuntimeError as r_err:
            if pytest:
                pytest.fail(f"Generator close raised RuntimeError: {r_err}")
            else:
                raise
    else:
        first_chunk = next(gen)
        assert first_chunk is not None
        try:
            gen.close()
        except RuntimeError as r_err:
            if pytest:
                pytest.fail(f"Generator close raised RuntimeError: {r_err}")
            else:
                raise


# ==============================================================================
# 12. TEST LRU EMBEDDING CACHING
# ==============================================================================

def test_lru_embedding_caching():
    """
    Verifies that get_query_embedding caches computed embeddings
    so that subsequent calls with the same normalized text do not re-run.
    """
    from app.core.redis_cache import get_query_embedding, _cached_embedding_tuple

    _cached_embedding_tuple.cache_clear()
    info_before = _cached_embedding_tuple.cache_info()

    q1 = "¿Cuáles son las fechas de sustentación de monografía?"
    emb1 = get_query_embedding(q1)
    assert len(emb1) > 0

    # Second call with case & accent variant
    q2 = "cuales son las fechas de sustentacion de monografia"
    emb2 = get_query_embedding(q2)
    assert emb1 == emb2

    info_after = _cached_embedding_tuple.cache_info()
    assert info_after.hits >= 1, "Expected LRU embedding cache hit for normalized query"


# ==============================================================================
# 13. UNITTEST TEST CASE RUNNER FOR STANDARD CLI TEST DISCOVERY
# ==============================================================================

import unittest

class TestRedisCacheCore(unittest.TestCase):
    def test_01_text_normalization(self):
        test_text_normalization()

    def test_02_unicode_smart_quotes(self):
        test_unicode_smart_quotes_and_symbols_normalization()

    def test_03_layer1_exact_match(self):
        test_layer1_exact_match_variants()

    def test_04_cosine_similarity(self):
        test_cosine_similarity_computation()

    def test_05_semantic_match_above_threshold(self):
        test_semantic_match_above_threshold()

    def test_06_rejection_below_threshold(self):
        test_rejection_below_threshold()

    def test_07_empty_whitespace_queries(self):
        test_empty_and_whitespace_queries()

    def test_08_ram_fallback_unconfigured(self):
        test_ram_fallback_unconfigured_redis()

    def test_09_ram_fallback_invalid_url(self):
        test_ram_fallback_invalid_redis_url()

    def test_10_ram_fallback_on_exception(self):
        test_ram_fallback_on_redis_runtime_exception()

    def test_11_ttl_expiration(self):
        test_ttl_expiration()

    def test_12_invalidate_all(self):
        test_invalidate_all()

    def test_13_delete_single_key(self):
        test_delete_single_key()

    def test_14_thread_safety(self):
        test_thread_safety_concurrent_access()

    def test_15_redis_operations_mocked(self):
        test_redis_operations_mocked()

    def test_16_lru_embedding_caching(self):
        test_lru_embedding_caching()


if __name__ == "__main__":
    unittest.main()


