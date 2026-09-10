import gc
import json
import time
import queue
import threading
from unittest.mock import patch, MagicMock
import pytest
import anyio
from starlette.requests import Request
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.security_guardrails import (
    STREAM_CONCURRENCY_SEMAPHORE,
    get_stream_capacity,
    get_active_stream_count,
    set_stream_capacity
)
from app.api.v1.chat import stream_chat_response, ChatRequest, SemaphoreReleaseGuard
from app.services.rag_service import rag_service, RAGService
from app.main import app


@pytest.fixture(autouse=True)
def reset_concurrency_semaphore():
    """Ensures clean baseline semaphore state before and after each test."""
    capacity = get_stream_capacity()
    STREAM_CONCURRENCY_SEMAPHORE._value = capacity
    yield
    STREAM_CONCURRENCY_SEMAPHORE._value = capacity


def _consume_response_body(response) -> list:
    """Helper to consume Starlette/FastAPI sync or async body_iterators cleanly."""
    it = response.body_iterator
    if hasattr(it, "__anext__"):
        async def _read():
            chunks = []
            async for chunk in it:
                if isinstance(chunk, bytes):
                    chunks.append(chunk.decode("utf-8"))
                else:
                    chunks.append(chunk)
            return chunks
        return anyio.run(_read)
    chunks = []
    for chunk in it:
        if isinstance(chunk, bytes):
            chunks.append(chunk.decode("utf-8"))
        else:
            chunks.append(chunk)
    return chunks


def _make_mock_request(client_ip: str = "10.10.10.10", path: str = "/api/v1/chat/stream") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "headers": [
            (b"x-forwarded-for", client_ip.encode()),
            (b"user-agent", b"pytest-concurrency-test"),
            (b"content-type", b"application/json")
        ],
        "path": path
    }
    return Request(scope)


def test_concurrency_capacity_configuration():
    """
    1. Verifies that STREAM_CONCURRENCY_LIMIT is configured to 150
       and SSE_KEEPALIVE_INTERVAL_SECONDS is configured to 15.0 by default.
    """
    assert settings.STREAM_CONCURRENCY_LIMIT == 150
    assert settings.SSE_KEEPALIVE_INTERVAL_SECONDS == 15.0
    assert get_stream_capacity() == 150
    assert get_active_stream_count() == 0


def test_concurrent_acquisition_and_503_saturation():
    """
    2. Simulates 150 concurrent stream slots acquiring successfully,
       verifies the 151st request receives HTTP 503 with Retry-After header,
       and verifies slots can be released and reclaimed cleanly.
    """
    # Ensure baseline is clean
    initial_active = get_active_stream_count()
    assert initial_active == 0, f"Expected 0 active streams, found {initial_active}"

    # Acquire all 150 slots
    capacity = get_stream_capacity()
    assert capacity == 150

    acquired_permits = []
    for i in range(capacity):
        ok = STREAM_CONCURRENCY_SEMAPHORE.acquire(blocking=False)
        assert ok is True, f"Failed to acquire permit #{i+1}"
        acquired_permits.append(ok)

    try:
        assert get_active_stream_count() == 150

        # Now the semaphore is 100% saturated.
        # The 151st request MUST be rejected with HTTP 503 and Retry-After
        mock_req = _make_mock_request(client_ip="192.168.100.1")
        payload = ChatRequest(query="¿Cuáles son los requisitos de pasantía?", history=[])
        mock_db = MagicMock()

        response = stream_chat_response(request=mock_req, payload=payload, db=mock_db)

        assert response.status_code == 503
        assert response.headers.get("Retry-After") == "5"

        # Verify friendly SSE notification in 503 stream body
        events = _consume_response_body(response)
        combined_text = "".join(events)
        assert "volumen muy alto" in combined_text
        assert "[DONE]" in combined_text

    finally:
        # Release all 150 acquired permits
        for _ in acquired_permits:
            STREAM_CONCURRENCY_SEMAPHORE.release()

    # Verify active count returns to 0
    assert get_active_stream_count() == 0

    # Verify that once released, a new request succeeds
    def mock_answer(q, h, emit_heartbeat=True):
        yield {"type": "token", "content": "Permit available again."}
        yield {"type": "citations", "citations": []}

    with patch("app.api.v1.chat.rag_service.answer_stream", side_effect=mock_answer):
        mock_req = _make_mock_request(client_ip="192.168.100.2")
        payload = ChatRequest(query="¿Puedo hacer monografía?", history=[])
        resp = stream_chat_response(request=mock_req, payload=payload, db=MagicMock())
        assert resp.status_code == 200
        events = _consume_response_body(resp)
        assert any("Permit available again." in e for e in events)

    assert get_active_stream_count() == 0


def test_keepalive_sse_heartbeat_on_slow_stream():
    """
    3. Verifies that when generation or retrieval takes longer than
       SSE_KEEPALIVE_INTERVAL_SECONDS, standard SSE comment frames
       (': ping\\n\\n') are emitted to prevent proxy timeouts.
    """
    # Configure low keepalive interval for fast deterministic testing
    with patch.object(settings, "SSE_KEEPALIVE_INTERVAL_SECONDS", 0.05):
        def slow_stream(query, history, emit_heartbeat=True):
            # First token
            yield {"type": "token", "content": "Iniciando respuesta..."}
            # Simulate a 120ms retrieval or LLM pause (2x the 50ms keepalive interval)
            time.sleep(0.12)
            yield {"type": "token", "content": " Continuando respuesta."}
            yield {"type": "citations", "citations": []}

        mock_req = _make_mock_request(client_ip="10.0.0.55")
        payload = ChatRequest(query="¿Cómo hacer la monografía paso a paso?", history=[])
        mock_db = MagicMock()

        with patch("app.api.v1.chat.rag_service.answer_stream", side_effect=slow_stream), \
             patch("app.api.v1.chat.redis_cache.get", return_value=None), \
             patch("app.api.v1.chat._submit_cache_write") as mock_cache:
            response = stream_chat_response(request=mock_req, payload=payload, db=mock_db)
            events = _consume_response_body(response)

        # Verify that : ping\n\n comments were emitted during the delay
        ping_events = [e for e in events if e == ": ping\n\n"]
        assert len(ping_events) >= 1, f"Expected at least 1 keepalive ping frame, got: {events}"

        # Verify that normal data frames are present and ordered
        token_events = [e for e in events if e.startswith("data: ") and "token" in e]
        assert len(token_events) == 2
        assert "Iniciando respuesta..." in token_events[0]
        assert "Continuando respuesta." in token_events[1]

        # Verify final [DONE] frame
        assert events[-1] == "data: [DONE]\n\n"

        # Verify cache write was submitted with only clean tokens (no ': ping' pollution)
        if mock_cache.called:
            cached_answer = mock_cache.call_args[0][1]
            assert ": ping" not in cached_answer
            assert "Iniciando respuesta... Continuando respuesta." == cached_answer

    assert get_active_stream_count() == 0


def test_rag_service_emit_heartbeat_flag():
    """
    4. Verifies that RAGService.answer_stream yields initial and pre-LLM
       {"type": "ping"} frames when emit_heartbeat=True, and omits them
       when emit_heartbeat=False (for backwards compatibility).
    """
    rag = RAGService()

    fake_results = [{
        "content": "Acuerdo 038 de 2015 sobre grados.",
        "metadata": {"title": "Acuerdo 038", "document_id": 1, "article": "Art 1"}
    }]

    # With emit_heartbeat=True:
    with patch("app.services.rag_service.vector_store.query", return_value=fake_results), \
         patch("app.services.rag_service.llm_adapter.stream_chat", return_value=iter(["Hola estudiante"])):
        events_with_ping = list(rag.answer_stream("¿Requisitos?", emit_heartbeat=True))

    types_with_ping = [e["type"] for e in events_with_ping]
    assert "ping" in types_with_ping
    assert "token" in types_with_ping
    assert types_with_ping[-1] == "citations"

    # With emit_heartbeat=False:
    with patch("app.services.rag_service.vector_store.query", return_value=fake_results), \
         patch("app.services.rag_service.llm_adapter.stream_chat", return_value=iter(["Hola estudiante"])):
        events_without_ping = list(rag.answer_stream("¿Requisitos?", emit_heartbeat=False))

    types_without_ping = [e["type"] for e in events_without_ping]
    assert "ping" not in types_without_ping
    assert "token" in types_without_ping
    assert types_without_ping[-1] == "citations"


def test_unconditional_semaphore_release_on_stream_completion():
    """
    5. Verifies that the semaphore permit is unconditionally acquired
       and released upon successful stream consumption.
    """
    assert get_active_stream_count() == 0

    def mock_answer(q, h, emit_heartbeat=True):
        yield {"type": "token", "content": "Respuesta normal."}
        yield {"type": "citations", "citations": []}

    mock_req = _make_mock_request(client_ip="10.10.10.1")
    payload = ChatRequest(query="¿Cómo inscribir trabajo de grado?", history=[])

    with patch("app.api.v1.chat.rag_service.answer_stream", side_effect=mock_answer):
        response = stream_chat_response(request=mock_req, payload=payload, db=MagicMock())
        # While generator is alive but before consumption, 1 slot is occupied
        assert get_active_stream_count() == 1

        # Consume the generator fully
        events = _consume_response_body(response)
        assert len(events) > 0

        # After consumption, slot MUST be unconditionally released
        assert get_active_stream_count() == 0


def test_unconditional_semaphore_release_on_mid_stream_exception():
    """
    6. Verifies that if an exception occurs mid-stream, the semaphore
       is unconditionally released in the finally block.
    """
    assert get_active_stream_count() == 0

    def failing_stream(q, h, emit_heartbeat=True):
        yield {"type": "token", "content": "Parte uno..."}
        raise RuntimeError("Conexión perdida con el proveedor LLM")

    mock_req = _make_mock_request(client_ip="10.10.10.2")
    payload = ChatRequest(query="¿Cuánto vale el semestre?", history=[])

    with patch("app.api.v1.chat.rag_service.answer_stream", side_effect=failing_stream):
        response = stream_chat_response(request=mock_req, payload=payload, db=MagicMock())
        assert get_active_stream_count() == 1

        # Consuming should catch the error and yield error message + [DONE]
        events = _consume_response_body(response)
        combined = "".join(events)
        assert "Error temporal en la transmisión" in combined
        assert "[DONE]" in combined

        # Semaphore permit MUST be released!
        assert get_active_stream_count() == 0


def test_unconditional_semaphore_release_on_client_disconnect_generator_exit():
    """
    7. Verifies that if a client prematurely disconnects mid-stream
       (which triggers GeneratorExit inside the generator), the semaphore
       permit is unconditionally released.
    """
    assert get_active_stream_count() == 0

    def infinite_stream(q, h, emit_heartbeat=True):
        for i in range(100):
            yield {"type": "token", "content": f"Token {i} "}
            time.sleep(0.01)

    mock_req = _make_mock_request(client_ip="10.10.10.3")
    payload = ChatRequest(query="Explicación larga sobre requisitos de grado...", history=[])

    with patch("app.api.v1.chat.rag_service.answer_stream", side_effect=infinite_stream):
        response = stream_chat_response(request=mock_req, payload=payload, db=MagicMock())
        assert get_active_stream_count() == 1

        it = response.body_iterator
        if hasattr(it, "__anext__"):
            async def _read_one_and_close():
                first = await it.__anext__()
                await it.aclose()
                return first
            first_chunk = anyio.run(_read_one_and_close)
        else:
            first_chunk = next(it)
            it.close()

        if isinstance(first_chunk, bytes):
            first_chunk = first_chunk.decode("utf-8")
        assert "Token" in first_chunk or "ping" in first_chunk

        # Semaphore MUST be released!
        assert get_active_stream_count() == 0


def test_unconditional_semaphore_release_on_abandoned_generator_gc():
    """
    8. Verifies that if a response generator is created (slot acquired)
       but never consumed and then garbage collected, SemaphoreReleaseGuard
       ensures the permit is safely released.
    """
    assert get_active_stream_count() == 0

    mock_req = _make_mock_request(client_ip="10.10.10.4")
    payload = ChatRequest(query="Consulta sobre monografía abandonada...", history=[])

    def mock_answer(q, h, emit_heartbeat=True):
        yield {"type": "token", "content": "abandonado"}

    with patch("app.api.v1.chat.rag_service.answer_stream", side_effect=mock_answer):
        response = stream_chat_response(request=mock_req, payload=payload, db=MagicMock())
        assert get_active_stream_count() == 1

        # Delete response without iterating and force gc
        del response
        gc.collect()

        assert get_active_stream_count() == 0


def test_semaphore_release_guard_idempotence():
    """
    9. Verifies that SemaphoreReleaseGuard is strictly idempotent
       and calling release() multiple times never increments semaphore beyond 1.
    """
    sem = threading.Semaphore(1)
    assert sem.acquire(blocking=False) is True
    assert sem._value == 0

    guard = SemaphoreReleaseGuard(sem)
    assert guard.released is False

    # First release -> increments permit to 1
    guard.release()
    assert guard.released is True
    assert sem._value == 1

    # Second and third calls -> NO-OP (no permit inflation)
    guard.release()
    guard.release()
    assert sem._value == 1

    # Destructor call -> NO-OP
    guard.__del__()
    assert sem._value == 1


def test_frontend_sse_comment_parser_compatibility():
    """
    10. Verifies frontend parser compatibility:
        Ensures that SSE comment frames (: ping\\n\\n) and comment lines
        starting with : are ignored cleanly without triggering JSON errors
        or emitting unwanted tokens.
    """
    # Simulated SSE chunks received over the network:
    raw_stream_chunks = [
        ": ping\n\n",
        ": ping\n\n",
        "data: {\"type\": \"token\", \"content\": \"El Acuerdo \"}\n\n",
        ": ping\ndata: {\"type\": \"token\", \"content\": \"038 de 2015 \"}\n\n",
        ": ping\n\n",
        "data: {\"type\": \"token\", \"content\": \"reglamenta los grados.\"}\n\n",
        "data: {\"type\": \"citations\", \"citations\": [{\"title\": \"Acuerdo 038\"}]}\n\n",
        "data: [DONE]\n\n"
    ]

    # Replicate the exact TypeScript parsing algorithm from frontend/src/lib/api.ts
    received_tokens = []
    received_citations = []
    stream_done = False

    def on_token(token: str):
        received_tokens.append(token)

    def on_citations(citations: list):
        received_citations.extend(citations)

    def on_done():
        nonlocal stream_done
        stream_done = True

    buffer = ""
    for chunk in raw_stream_chunks:
        buffer += chunk
        lines = buffer.split("\n\n")
        buffer = lines.pop() or ""

        for block in lines:
            block_lines = block.split("\n")
            for raw_line in block_lines:
                trimmed = raw_line.strip()
                if not trimmed or trimmed.startswith(":"):
                    continue
                if not trimmed.startswith("data:"):
                    continue

                data_str = trimmed[5:].strip()
                if data_str == "[DONE]":
                    on_done()
                    break

                try:
                    parsed = json.loads(data_str)
                    if parsed.get("type") == "token" and parsed.get("content"):
                        on_token(parsed["content"])
                    elif parsed.get("type") == "citations" and parsed.get("citations"):
                        on_citations(parsed["citations"])
                except Exception:
                    pass

    # Verify results
    assert stream_done is True
    full_text = "".join(received_tokens)
    assert full_text == "El Acuerdo 038 de 2015 reglamenta los grados."
    assert ": ping" not in full_text
    assert len(received_citations) == 1
    assert received_citations[0]["title"] == "Acuerdo 038"


def test_concurrent_threads_load_safety():
    """
    11. Concurrency safety test with 25 concurrent threads simultaneously
        calling the streaming endpoint. Verifies all acquire and release
        slots safely without race conditions or leaks.
    """
    def mock_answer(q, h, emit_heartbeat=True):
        time.sleep(0.02)
        yield {"type": "token", "content": "Concurrencia segura."}
        yield {"type": "citations", "citations": []}

    errors = []
    completed = []

    def worker_request(thread_id: int):
        try:
            req = _make_mock_request(client_ip=f"10.0.1.{thread_id}")
            payload = ChatRequest(query=f"Pregunta sobre monografía hilo {thread_id}", history=[])
            with patch("app.api.v1.chat.rag_service.answer_stream", side_effect=mock_answer), \
                 patch("app.api.v1.chat.redis_cache.get", return_value=None), \
                 patch("app.api.v1.chat._submit_cache_write"):
                resp = stream_chat_response(request=req, payload=payload, db=MagicMock())
                assert resp.status_code == 200
                events = _consume_response_body(resp)
                assert any("Concurrencia segura." in e for e in events)
                completed.append(thread_id)
        except Exception as e:
            errors.append((thread_id, str(e)))

    threads = [threading.Thread(target=worker_request, args=(i,)) for i in range(25)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(errors) == 0, f"Thread errors encountered: {errors}"
    assert len(completed) == 25
    # Ensure zero leak
    assert get_active_stream_count() == 0
