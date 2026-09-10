import time
import json
import threading
from unittest.mock import patch, MagicMock
import pytest
import anyio
from starlette.requests import Request

from app.core.config import settings
from app.core.security_guardrails import (
    STREAM_CONCURRENCY_SEMAPHORE,
    get_stream_capacity,
    get_active_stream_count,
    set_stream_capacity
)
from app.core.virtual_queue import virtual_queue, VirtualQueueManager, QueueTicket
from app.api.v1.chat import stream_chat_response, ChatRequest


@pytest.fixture(autouse=True)
def reset_concurrency_and_queue():
    """Ensures clean baseline semaphore and queue state before and after each test."""
    virtual_queue.reset()
    capacity = get_stream_capacity()
    STREAM_CONCURRENCY_SEMAPHORE._value = capacity
    yield
    virtual_queue.reset()
    capacity = get_stream_capacity()
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
            (b"user-agent", b"pytest-virtual-queue-test"),
            (b"content-type", b"application/json")
        ],
        "path": path
    }
    return Request(scope)


def test_virtual_queue_configuration():
    """
    1. Verifies that QUEUE_MAX_WAIT_SECONDS is 15.0 and QUEUE_CAPACITY is 100 by default.
    """
    assert settings.QUEUE_MAX_WAIT_SECONDS == 15.0
    assert settings.QUEUE_CAPACITY == 100
    assert virtual_queue.get_capacity() == 100
    assert virtual_queue.get_max_wait_seconds() == 15.0
    assert virtual_queue.get_queue_length() == 0
    assert virtual_queue.has_waiters() is False


def test_virtual_queue_unit_operations():
    """
    2. Tests core queue mechanics: enqueueing, FIFO position tracking,
       ticket removal, and position re-indexing.
    """
    t1 = virtual_queue.enqueue()
    t2 = virtual_queue.enqueue()
    t3 = virtual_queue.enqueue()

    assert t1 is not None and t1.position == 1
    assert t2 is not None and t2.position == 2
    assert t3 is not None and t3.position == 3
    assert virtual_queue.get_queue_length() == 3
    assert virtual_queue.has_waiters() is True

    # Remove t1 (head of queue)
    virtual_queue.remove_ticket(t1)
    assert virtual_queue.get_queue_length() == 2
    assert t2.position == 1
    assert t3.position == 2

    # Reset
    virtual_queue.reset()
    assert virtual_queue.get_queue_length() == 0
    assert virtual_queue.has_waiters() is False


def test_virtual_queue_capacity_saturation_rejection():
    """
    3. Tests that when queue capacity is exceeded (or set to 0),
       new requests are immediately rejected with HTTP 503 and Retry-After.
    """
    virtual_queue.set_capacity(2)

    # Fill queue to capacity
    t1 = virtual_queue.enqueue()
    t2 = virtual_queue.enqueue()
    assert t1 is not None and t2 is not None
    assert virtual_queue.is_full() is True

    # 3rd enqueue should fail
    t3 = virtual_queue.enqueue()
    assert t3 is None

    # Test rejection through stream_chat_response
    mock_req = _make_mock_request(client_ip="192.168.1.50")
    payload = ChatRequest(query="¿Cómo solicitar grado por ventanilla?", history=[])

    # Hold all 150 permits so it cannot acquire directly
    capacity = get_stream_capacity()
    held = [STREAM_CONCURRENCY_SEMAPHORE.acquire(blocking=False) for _ in range(capacity)]
    try:
        response = stream_chat_response(request=mock_req, payload=payload, db=MagicMock())
        assert response.status_code == 503
        assert response.headers.get("Retry-After") == "5"

        events = _consume_response_body(response)
        combined = "".join(events)
        assert "volumen muy alto" in combined
        assert "[DONE]" in combined
    finally:
        for _ in held:
            STREAM_CONCURRENCY_SEMAPHORE.release()


def test_virtual_queue_entry_and_event_emission():
    """
    4. Verifies that when the 150 semaphore permits are exhausted,
       the request enters the virtual queue and immediately emits:
       data: {"type": "queue", "position": 1, "estimated_seconds": X}
    """
    capacity = get_stream_capacity()
    held = [STREAM_CONCURRENCY_SEMAPHORE.acquire(blocking=False) for _ in range(capacity)]

    try:
        mock_req = _make_mock_request(client_ip="10.20.30.40")
        payload = ChatRequest(query="¿Cuáles son los requisitos de grado?", history=[])

        response = stream_chat_response(request=mock_req, payload=payload, db=MagicMock())
        assert response.status_code == 503
        assert response.headers.get("Retry-After") == "5"

        # Read only the first chunk from the iterator
        it = response.body_iterator
        if hasattr(it, "__anext__"):
            async def _read_first():
                return await it.__anext__()
            first_chunk = anyio.run(_read_first)
        else:
            first_chunk = next(it)

        if isinstance(first_chunk, bytes):
            first_chunk = first_chunk.decode("utf-8")

        assert "data: " in first_chunk
        assert '"type": "queue"' in first_chunk
        assert '"position": 1' in first_chunk
        assert "estimated_seconds" in first_chunk

        # Verify queue state
        assert virtual_queue.get_queue_length() == 1

        # Close iterator to clean up
        if hasattr(it, "aclose"):
            anyio.run(it.aclose)
        elif hasattr(it, "close"):
            it.close()

    finally:
        for _ in held:
            STREAM_CONCURRENCY_SEMAPHORE.release()


def test_virtual_queue_advancement_and_slot_acquisition():
    """
    5. Tests queue advancement and permit acquisition:
       - Semaphore is saturated.
       - Request enters queue and receives 'queue' event.
       - Another active stream finishes and releases permit.
       - Queued request acquires slot, receives 'queue_ready' event,
         and streams response tokens to completion.
    """
    capacity = get_stream_capacity()
    held = [STREAM_CONCURRENCY_SEMAPHORE.acquire(blocking=False) for _ in range(capacity)]

    def mock_answer(q, h, emit_heartbeat=True):
        yield {"type": "token", "content": "Respuesta tras salir de la fila."}
        yield {"type": "citations", "citations": [{"title": "Acuerdo 038"}]}

    try:
        mock_req = _make_mock_request(client_ip="10.20.30.41")
        payload = ChatRequest(query="¿Puedo hacer pasantía como opción de grado?", history=[])

        # Release one permit after ticket is enqueued to simulate an active stream finishing
        def delayed_release():
            for _ in range(100):
                if virtual_queue.get_queue_length() > 0:
                    break
                time.sleep(0.01)
            time.sleep(0.05)
            STREAM_CONCURRENCY_SEMAPHORE.release()
            virtual_queue.notify_available()

        release_thread = threading.Thread(target=delayed_release, daemon=True)
        release_thread.start()

        with patch("app.api.v1.chat.rag_service.answer_stream", side_effect=mock_answer):
            response = stream_chat_response(request=mock_req, payload=payload, db=MagicMock())
            events = _consume_response_body(response)

        release_thread.join(timeout=2.0)

        # Verify event sequence:
        combined = "".join(events)
        assert '"type": "queue"' in combined
        assert '"type": "queue_ready"' in combined
        assert "Respuesta tras salir de la fila." in combined
        assert "Acuerdo 038" in combined
        assert "[DONE]" in combined

        # Verify active count is clean after stream completion
        assert get_active_stream_count() == capacity - 1  # since we released 1 permit permanently
        assert virtual_queue.get_queue_length() == 0

    finally:
        # Release the remaining 149 permits
        for _ in range(capacity - 1):
            STREAM_CONCURRENCY_SEMAPHORE.release()


def test_virtual_queue_timeout_graceful_degradation():
    """
    6. Verifies graceful degradation on queue timeout:
       - Configures a short timeout (e.g. 0.15s).
       - Semaphore remains saturated throughout.
       - Verifies stream emits 'queue', keepalive pings, and then the graceful
         degradation message with 1-click retry recommendation before [DONE].
    """
    capacity = get_stream_capacity()
    held = [STREAM_CONCURRENCY_SEMAPHORE.acquire(blocking=False) for _ in range(capacity)]

    try:
        virtual_queue.set_max_wait_seconds(0.15)

        mock_req = _make_mock_request(client_ip="10.20.30.42")
        payload = ChatRequest(query="¿Cómo inscribir monografía?", history=[])

        response = stream_chat_response(request=mock_req, payload=payload, db=MagicMock())
        events = _consume_response_body(response)

        combined = "".join(events)
        # 1. Received initial queue banner
        assert '"type": "queue"' in combined
        # 2. Never received queue_ready because slots never freed up
        assert '"type": "queue_ready"' not in combined
        # 3. Received graceful saturation message with 1-click retry recommendation
        assert "volumen muy alto" in combined or "expirado" in combined
        assert "reintenta" in combined.lower()
        # 4. Stream completed cleanly with [DONE]
        assert "[DONE]" in combined

        # 5. Queue ticket was cleaned up
        assert virtual_queue.get_queue_length() == 0

    finally:
        virtual_queue.set_max_wait_seconds(15.0)
        for _ in held:
            STREAM_CONCURRENCY_SEMAPHORE.release()


def test_virtual_queue_client_disconnect_cleanup():
    """
    7. Verifies that if a queued client disconnects (GeneratorExit),
       their ticket is cleanly removed from the virtual queue without leaking state.
    """
    capacity = get_stream_capacity()
    held = [STREAM_CONCURRENCY_SEMAPHORE.acquire(blocking=False) for _ in range(capacity)]

    try:
        mock_req = _make_mock_request(client_ip="10.20.30.43")
        payload = ChatRequest(query="¿Cuáles son los requisitos de pasantía para grado universitario?", history=[])

        response = stream_chat_response(request=mock_req, payload=payload, db=MagicMock())
        assert virtual_queue.get_queue_length() == 1

        it = response.body_iterator
        if hasattr(it, "__anext__"):
            async def _read_one_and_cancel():
                first = await it.__anext__()
                await it.aclose()
                return first
            anyio.run(_read_one_and_cancel)
        else:
            first = next(it)
        del response, it
        import gc
        gc.collect()

        # Ticket MUST be removed from virtual queue
        assert virtual_queue.get_queue_length() == 0

    finally:
        for _ in held:
            STREAM_CONCURRENCY_SEMAPHORE.release()


def test_virtual_queue_cascading_wake_up():
    """
    8. Tests that when multiple permits become available, claiming a permit
       cascades immediately and wakes the next queued ticket without 1-second delays.
    """
    sem = threading.Semaphore(0)
    t1 = virtual_queue.enqueue()
    t2 = virtual_queue.enqueue()
    t3 = virtual_queue.enqueue()

    assert t1 is not None and t2 is not None and t3 is not None
    assert virtual_queue.get_queue_length() == 3

    claimed = []

    def waiter(ticket):
        while not ticket.acquired and not ticket.cancelled:
            if virtual_queue.try_claim_permit(ticket, sem):
                claimed.append(ticket.ticket_id)
                break
            ticket.wait(timeout=1.0)

    th1 = threading.Thread(target=waiter, args=(t1,), daemon=True)
    th2 = threading.Thread(target=waiter, args=(t2,), daemon=True)
    th1.start()
    th2.start()

    # Release 2 permits at once
    t_start = time.time()
    sem.release()
    sem.release()
    virtual_queue.notify_available()

    th1.join(timeout=0.5)
    th2.join(timeout=0.5)
    elapsed = time.time() - t_start

    # Both tickets should have acquired permits within <0.5s (no 1-second timeout stall)
    assert t1.acquired is True
    assert t2.acquired is True
    assert len(claimed) == 2
    assert elapsed < 0.5, f"Expected cascade to take <0.5s, took {elapsed}s"
    assert virtual_queue.get_queue_length() == 1
    assert t3.position == 1

    virtual_queue.reset()


def test_virtual_queue_ticket_flags_integrity():
    """
    9. Tests that acquired tickets maintain acquired=True and cancelled=False,
       while removed/cancelled tickets have cancelled=True.
    """
    sem = threading.Semaphore(1)
    t1 = virtual_queue.enqueue()
    t2 = virtual_queue.enqueue()

    # t1 claims permit
    ok = virtual_queue.try_claim_permit(t1, sem)
    assert ok is True
    assert t1.acquired is True
    assert t1.cancelled is False

    # Calling remove_ticket on acquired ticket does NOT corrupt cancelled flag
    virtual_queue.remove_ticket(t1)
    assert t1.acquired is True
    assert t1.cancelled is False

    # t2 is removed without acquiring
    virtual_queue.remove_ticket(t2)
    assert t2.acquired is False
    assert t2.cancelled is True

    virtual_queue.reset()


def test_virtual_queue_permit_no_leak_on_immediate_disconnect():
    """
    10. Verifies that if a client disconnects immediately after acquiring a slot,
        the semaphore permit is freed and never leaked.
    """
    capacity = get_stream_capacity()
    held = [STREAM_CONCURRENCY_SEMAPHORE.acquire(blocking=False) for _ in range(capacity)]

    def delayed_release():
        for _ in range(100):
            if virtual_queue.get_queue_length() > 0:
                break
            time.sleep(0.01)
        time.sleep(0.05)
        STREAM_CONCURRENCY_SEMAPHORE.release()
        virtual_queue.notify_available()

    release_thread = threading.Thread(target=delayed_release, daemon=True)

    try:
        mock_req = _make_mock_request(client_ip="10.20.30.44")
        payload = ChatRequest(query="¿Cómo inscribir asignaturas de posgrado?", history=[])

        def mock_infinite(q, h, emit_heartbeat=True):
            for i in range(100):
                yield {"type": "token", "content": f"token {i} "}
                time.sleep(0.02)

        with patch("app.api.v1.chat.rag_service.answer_stream", side_effect=mock_infinite):
            release_thread.start()
            response = stream_chat_response(request=mock_req, payload=payload, db=MagicMock())
            it = response.body_iterator

            # Consume the queue event, then queue_ready and a token, then close
            if hasattr(it, "__anext__"):
                import anyio
                async def _consume_part_and_close():
                    e1 = await it.__anext__()
                    e2 = await it.__anext__()
                    await it.aclose()
                    return e1, e2
                anyio.run(_consume_part_and_close)
            else:
                next(it)
                next(it)
                if hasattr(it, "close"):
                    it.close()

            release_thread.join(timeout=2.0)
            del response, it
            import gc
            gc.collect()

            # The released permit must be back in the semaphore (not leaked)
            assert get_active_stream_count() == capacity - 1

    finally:
        for _ in range(capacity - 1):
            STREAM_CONCURRENCY_SEMAPHORE.release()

