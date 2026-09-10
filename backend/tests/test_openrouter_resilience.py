import json
import time
from typing import List, Dict, Any
from unittest.mock import MagicMock, patch, call
import pytest
import httpx
import openai

from app.core.config import Settings, settings
from app.services.llm_adapter import LLMAdapter, is_transient_error
from app.services.rag_service import RAGService


# Helper to build mock openai responses
def make_mock_chunk(content: str):
    delta = MagicMock()
    delta.content = content
    choice = MagicMock()
    choice.delta = delta
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def make_mock_completion(content: str):
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def make_mock_openai_error(status_code: int, message: str = "Error"):
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    resp = httpx.Response(status_code=status_code, request=req)
    if status_code == 429:
        return openai.RateLimitError(message=message, response=resp, body=None)
    elif status_code in (500, 502, 503, 504):
        return openai.InternalServerError(message=message, response=resp, body=None)
    elif status_code == 401:
        return openai.AuthenticationError(message=message, response=resp, body=None)
    else:
        return openai.APIStatusError(message=message, response=resp, body=None)


# ==============================================================================
# 1. CONFIGURATION & VALIDATORS TESTS
# ==============================================================================

def test_config_fallback_models_comma_separated():
    """Verifies that OPENROUTER_FALLBACK_MODELS correctly parses comma-separated strings."""
    s = Settings(
        OPENROUTER_FALLBACK_MODELS="meta-llama/llama-3.3-70b-instruct,google/gemini-2.0-flash-001,openai/gpt-4o-mini"
    )
    assert s.OPENROUTER_FALLBACK_MODELS == [
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.0-flash-001",
        "openai/gpt-4o-mini"
    ]


def test_config_fallback_models_json_array():
    """Verifies that OPENROUTER_FALLBACK_MODELS correctly parses JSON array strings."""
    s = Settings(
        OPENROUTER_FALLBACK_MODELS='["meta-llama/llama-3.3-70b-instruct", "google/gemini-2.0-flash-001"]'
    )
    assert s.OPENROUTER_FALLBACK_MODELS == [
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.0-flash-001"
    ]


def test_config_resilience_defaults():
    """Verifies default values for OpenRouter resilience settings."""
    assert settings.OPENROUTER_TIMEOUT == 30.0
    assert settings.OPENROUTER_MAX_RETRIES == 3
    assert settings.OPENROUTER_BACKOFF_FACTOR == 1.5
    assert len(settings.OPENROUTER_FALLBACK_MODELS) >= 2
    assert "meta-llama/llama-3.3-70b-instruct" in settings.OPENROUTER_FALLBACK_MODELS


# ==============================================================================
# 2. MODELS LIST & DEDUPLICATION TESTS
# ==============================================================================

def test_get_openrouter_models_order_and_deduplication():
    """
    Verifies that get_openrouter_models builds [primary, *fallbacks]
    in the exact order, without duplicating the primary model.
    """
    adapter = LLMAdapter()
    adapter.model_name = "meta-llama/llama-3.1-8b-instruct"

    with patch.object(settings, "OPENROUTER_FALLBACK_MODELS", [
        "meta-llama/llama-3.1-8b-instruct",  # Duplicate of primary
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.0-flash-001"
    ]):
        models = adapter.get_openrouter_models()
        assert models == [
            "meta-llama/llama-3.1-8b-instruct",
            "meta-llama/llama-3.3-70b-instruct",
            "google/gemini-2.0-flash-001"
        ]
        # Primary is first and appears exactly once
        assert models[0] == "meta-llama/llama-3.1-8b-instruct"
        assert models.count("meta-llama/llama-3.1-8b-instruct") == 1


# ==============================================================================
# 3. OPENROUTER PAYLOAD VERIFICATION (MODELS PARAMETER & TIMEOUT)
# ==============================================================================

def test_openrouter_payload_contains_models_in_stream():
    """
    Verifies that stream_chat passes extra_body={'models': [...]}
    and timeout=OPENROUTER_TIMEOUT to client.chat.completions.create.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"
    adapter.model_name = "meta-llama/llama-3.1-8b-instruct"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = [
        make_mock_chunk("Respuesta "),
        make_mock_chunk("exitosa.")
    ]
    adapter.client = mock_client

    messages = [{"role": "user", "content": "¿Cómo hago la pasantía?"}]

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"), \
         patch.object(settings, "OPENROUTER_FALLBACK_MODELS", [
             "meta-llama/llama-3.3-70b-instruct",
             "google/gemini-2.0-flash-001"
         ]):
        chunks = list(adapter.stream_chat(messages))

    assert "".join(chunks) == "Respuesta exitosa."
    assert mock_client.chat.completions.create.call_count == 1

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "meta-llama/llama-3.1-8b-instruct"
    assert call_kwargs["stream"] is True
    assert call_kwargs["timeout"] == settings.OPENROUTER_TIMEOUT
    assert "extra_body" in call_kwargs
    assert call_kwargs["extra_body"]["models"] == [
        "meta-llama/llama-3.1-8b-instruct",
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.0-flash-001"
    ]


def test_openrouter_payload_contains_models_in_chat_completion():
    """
    Verifies that non-streaming chat_completion passes extra_body={'models': [...]}
    and timeout to client.chat.completions.create.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"
    adapter.model_name = "meta-llama/llama-3.1-8b-instruct"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = make_mock_completion("Información de pasantía.")
    adapter.client = mock_client

    messages = [{"role": "user", "content": "Requisitos"}]

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"), \
         patch.object(settings, "OPENROUTER_FALLBACK_MODELS", [
             "meta-llama/llama-3.3-70b-instruct",
             "google/gemini-2.0-flash-001"
         ]):
        result = adapter.chat_completion(messages)

    assert result == "Información de pasantía."
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "meta-llama/llama-3.1-8b-instruct"
    assert call_kwargs["stream"] is False
    assert call_kwargs["timeout"] == 30.0
    assert call_kwargs["extra_body"]["models"] == [
        "meta-llama/llama-3.1-8b-instruct",
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.0-flash-001"
    ]


def test_openrouter_payload_contains_models_in_generate_json():
    """
    Verifies that generate_json passes extra_body={'models': [...]}
    and timeout to client.chat.completions.create.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"
    adapter.model_name = "meta-llama/llama-3.1-8b-instruct"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = make_mock_completion(
        json.dumps({"is_relevant": True, "relevance_score": 95.0})
    )
    adapter.client = mock_client

    messages = [{"role": "user", "content": "Convocatoria pasantías 2026"}]

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"), \
         patch.object(settings, "OPENROUTER_FALLBACK_MODELS", [
             "meta-llama/llama-3.3-70b-instruct",
             "google/gemini-2.0-flash-001"
         ]):
        res = adapter.generate_json(messages)

    assert res["is_relevant"] is True
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["timeout"] == 30.0
    assert call_kwargs["extra_body"]["models"] == [
        "meta-llama/llama-3.1-8b-instruct",
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.0-flash-001"
    ]


# ==============================================================================
# 4. EXPONENTIAL BACKOFF RETRY ON TRANSIENT ERRORS (429, 503, CONNECTION)
# ==============================================================================

@patch("time.sleep", return_value=None)
def test_retry_on_429_rate_limit(mock_sleep):
    """
    Tests exponential backoff retry when receiving HTTP 429 Too Many Requests.
    Verifies that sleep is called with backoff_factor ** attempt.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"

    err_429 = make_mock_openai_error(429, "Rate limit exceeded")
    success_resp = [make_mock_chunk("Éxito tras 429")]

    mock_client = MagicMock()
    # 1st call: 429, 2nd call: success
    mock_client.chat.completions.create.side_effect = [err_429, success_resp]
    adapter.client = mock_client

    messages = [{"role": "user", "content": "Hola"}]

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"), \
         patch.object(settings, "OPENROUTER_BACKOFF_FACTOR", 1.5):
        chunks = list(adapter.stream_chat(messages))

    assert "".join(chunks) == "Éxito tras 429"
    assert mock_client.chat.completions.create.call_count == 2
    # Verify exponential sleep was invoked for attempt 1 (1.5 ** 1 = 1.5s)
    mock_sleep.assert_called_once_with(1.5)


@patch("time.sleep", return_value=None)
def test_retry_on_503_service_unavailable(mock_sleep):
    """
    Tests retry on HTTP 503 Service Unavailable across multiple attempts.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"

    err_503 = make_mock_openai_error(503, "Service Unavailable")
    success_resp = [make_mock_chunk("Recuperado de 503")]

    mock_client = MagicMock()
    # 2 failures with 503, then success on 3rd attempt
    mock_client.chat.completions.create.side_effect = [err_503, err_503, success_resp]
    adapter.client = mock_client

    messages = [{"role": "user", "content": "Consulta"}]

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"), \
         patch.object(settings, "OPENROUTER_BACKOFF_FACTOR", 2.0):
        chunks = list(adapter.stream_chat(messages))

    assert "".join(chunks) == "Recuperado de 503"
    assert mock_client.chat.completions.create.call_count == 3
    # Two sleeps: 2.0 ** 1 = 2.0s, 2.0 ** 2 = 4.0s
    assert mock_sleep.call_count == 2
    assert mock_sleep.call_args_list == [call(2.0), call(4.0)]


@patch("time.sleep", return_value=None)
def test_retry_on_connection_error_and_timeout(mock_sleep):
    """
    Tests retry on network connection errors and API timeouts.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"

    req = httpx.Request("POST", "https://openrouter.ai")
    err_conn = openai.APIConnectionError(request=req)
    err_timeout = openai.APITimeoutError(request=req)
    success_resp = [make_mock_chunk("Conexión restaurada")]

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [err_conn, err_timeout, success_resp]
    adapter.client = mock_client

    messages = [{"role": "user", "content": "Test"}]

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"):
        chunks = list(adapter.stream_chat(messages))

    assert "".join(chunks) == "Conexión restaurada"
    assert mock_client.chat.completions.create.call_count == 3
    assert mock_sleep.call_count == 2


# ==============================================================================
# 5. CLEAN STREAM RETRY BEFORE TOKEN EMISSION
# ==============================================================================

@patch("time.sleep", return_value=None)
def test_streaming_clean_retry_before_tokens_emitted(mock_sleep):
    """
    Verifies that when a failure occurs BEFORE any tokens have been yielded,
    the generator restarts cleanly and yields the complete response without duplicates.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"

    err_502 = make_mock_openai_error(502, "Bad Gateway")
    success_chunks = [
        make_mock_chunk("Primer "),
        make_mock_chunk("token, "),
        make_mock_chunk("segundo token.")
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [err_502, success_chunks]
    adapter.client = mock_client

    messages = [{"role": "user", "content": "Pregunta"}]

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"):
        emitted = list(adapter.stream_chat(messages))

    assert emitted == ["Primer ", "token, ", "segundo token."]
    assert mock_client.chat.completions.create.call_count == 2


# ==============================================================================
# 6. EXHAUSTION OF RETRIES & GRACEFUL DEGRADATION
# ==============================================================================

@patch("time.sleep", return_value=None)
def test_stream_exhaustion_graceful_error(mock_sleep):
    """
    Verifies that when all retries are exhausted in streaming mode,
    an informative error chunk is yielded rather than raising an unhandled exception.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"

    err_429 = make_mock_openai_error(429, "Too Many Requests")
    mock_client = MagicMock()
    # Always fails
    mock_client.chat.completions.create.side_effect = err_429
    adapter.client = mock_client

    messages = [{"role": "user", "content": "Pregunta"}]

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"), \
         patch.object(settings, "OPENROUTER_MAX_RETRIES", 2):
        chunks = list(adapter.stream_chat(messages))

    full_output = "".join(chunks)
    assert "[Error de comunicación con el modelo LLM" in full_output
    assert "Too Many Requests" in full_output
    # 1 initial + 2 retries = 3 calls
    assert mock_client.chat.completions.create.call_count == 3
    assert mock_sleep.call_count == 2


@patch("time.sleep", return_value=None)
def test_generate_json_exhaustion_contingency_fallback(mock_sleep):
    """
    Verifies that when generate_json exhausts all retries,
    it gracefully degrades to the heuristic triage response.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"

    err_503 = make_mock_openai_error(503, "Service Unavailable")
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = err_503
    adapter.client = mock_client

    messages = [{"role": "user", "content": "Aviso oficial sobre pasantias en sistemas"}]

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"), \
         patch.object(settings, "OPENROUTER_MAX_RETRIES", 2):
        result = adapter.generate_json(messages)

    assert isinstance(result, dict)
    assert result["is_relevant"] is True
    assert result["recommended_action"] == "INDEX"
    assert "contingencia" in result["summary"].lower() or "contingencia" in result["reasoning"].lower()
    # 1 initial + 2 retries = 3 calls
    assert mock_client.chat.completions.create.call_count == 3


# ==============================================================================
# 7. MID-STREAM ERROR RECOVERY
# ==============================================================================

def test_mid_stream_interruption_does_not_crash():
    """
    Verifies that if a stream is interrupted mid-generation (after tokens were emitted),
    it does NOT attempt an unsafe restart (which would cause repeated text)
    and instead yields a polite interruption message without crashing.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"

    def faulty_generator():
        yield make_mock_chunk("Los requisitos ")
        yield make_mock_chunk("son: 1. Créditos 80%, ")
        # Connection severed mid-generation
        req = httpx.Request("POST", "https://openrouter.ai")
        raise openai.APIConnectionError(request=req)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = faulty_generator()
    adapter.client = mock_client

    messages = [{"role": "user", "content": "¿Requisitos?"}]

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"):
        chunks = list(adapter.stream_chat(messages))

    full_text = "".join(chunks)
    assert "Los requisitos son: 1. Créditos 80%, " in full_text
    assert "Conexión interrumpida durante la generación" in full_text
    # Should NOT have retried or called create again
    assert mock_client.chat.completions.create.call_count == 1


def test_rag_service_guarantees_citations_on_mid_stream_error():
    """
    Verifies that RAGService.answer_stream yields token chunks,
    handles any mid-stream interruption gracefully, and GUARANTEES
    that the final 'citations' event is emitted to the client.
    """
    rag = RAGService()

    def faulty_stream(*args, **kwargs):
        yield "Información parcial sobre monografía."
        raise RuntimeError("Unexpected connection reset")

    with patch("app.services.rag_service.vector_store.query", return_value=[
        {
            "content": "Artículo 18: Monografía a partir del 70%.",
            "metadata": {
                "title": "Acuerdo 038 de 2015",
                "resolution_number": "Acuerdo 038",
                "article": "Artículo 18",
                "document_id": 42
            }
        }
    ]), patch("app.services.rag_service.llm_adapter.stream_chat", side_effect=faulty_stream):
        events = list(rag.answer_stream("¿Requisitos monografía?"))

    types = [e["type"] for e in events]
    assert "token" in types
    assert "citations" in types
    assert types[-1] == "citations"

    # Verify citation was preserved
    citations_event = events[-1]
    assert len(citations_event["citations"]) == 1
    assert citations_event["citations"][0]["title"] == "Acuerdo 038 de 2015"


# ==============================================================================
# 8. NON-TRANSIENT ERROR ABORT (NO ENDLESS RETRIES)
# ==============================================================================

@patch("time.sleep", return_value=None)
def test_non_transient_error_aborts_immediately(mock_sleep):
    """
    Verifies that permanent errors (e.g. 401 Unauthorized)
    abort immediately on the first attempt without retrying.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"

    err_401 = make_mock_openai_error(401, "Invalid API Key")
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = err_401
    adapter.client = mock_client

    messages = [{"role": "user", "content": "Hola"}]

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"), \
         patch.object(settings, "OPENROUTER_MAX_RETRIES", 3):
        chunks = list(adapter.stream_chat(messages))

    full_output = "".join(chunks)
    assert "[Error de comunicación con el modelo LLM" in full_output
    assert "Invalid API Key" in full_output
    # Must NOT retry: exactly 1 attempt
    assert mock_client.chat.completions.create.call_count == 1
    assert mock_sleep.call_count == 0


# ==============================================================================
# 9. TRANSIENT ERROR DETECTOR UNIT TEST
# ==============================================================================

def test_is_transient_error_coverage():
    """Verifies that is_transient_error identifies all specified transient errors."""
    req = httpx.Request("POST", "https://openrouter.ai")

    assert is_transient_error(openai.RateLimitError("429", response=httpx.Response(429, request=req), body=None)) is True
    assert is_transient_error(openai.InternalServerError("503", response=httpx.Response(503, request=req), body=None)) is True
    assert is_transient_error(openai.InternalServerError("502", response=httpx.Response(502, request=req), body=None)) is True
    assert is_transient_error(openai.InternalServerError("504", response=httpx.Response(504, request=req), body=None)) is True
    assert is_transient_error(openai.APIConnectionError(request=req)) is True
    assert is_transient_error(openai.APITimeoutError(request=req)) is True
    assert is_transient_error(httpx.ConnectError("Connection failed", request=req)) is True
    assert is_transient_error(httpx.TimeoutException("Read timed out")) is True
    assert is_transient_error(RuntimeError("503 Service Unavailable")) is True

    # Permanent errors must NOT be transient
    assert is_transient_error(openai.AuthenticationError("401", response=httpx.Response(401, request=req), body=None)) is False
    assert is_transient_error(ValueError("Invalid model parameter")) is False


# ==============================================================================
# 10. ADDITIONAL EDGE CASE TESTS
# ==============================================================================

@patch("time.sleep", return_value=None)
def test_chat_completion_retry_and_exhaustion(mock_sleep):
    """
    Verifies that chat_completion retries on transient errors and raises on exhaustion.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"

    err_502 = make_mock_openai_error(502, "Bad Gateway")
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = err_502
    adapter.client = mock_client

    messages = [{"role": "user", "content": "Test"}]

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"), \
         patch.object(settings, "OPENROUTER_MAX_RETRIES", 2):
        with pytest.raises(openai.InternalServerError):
            adapter.chat_completion(messages)

    # 1 initial + 2 retries = 3 calls
    assert mock_client.chat.completions.create.call_count == 3
    assert mock_sleep.call_count == 2


def test_non_openrouter_provider_does_not_add_models_payload():
    """
    Verifies that non-OpenRouter providers (e.g. standard openai)
    do NOT pass OpenRouter's extra_body={'models': ...}.
    """
    adapter = LLMAdapter()
    adapter.provider = "openai"
    adapter.model_name = "gpt-4o-mini"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = [make_mock_chunk("OpenAI standard response")]
    adapter.client = mock_client

    messages = [{"role": "user", "content": "Test"}]

    with patch.object(settings, "OPENAI_API_KEY", "sk-openai-key"):
        list(adapter.stream_chat(messages))

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert "extra_body" not in call_kwargs


def test_stream_chat_demo_mode_when_dummy_key():
    """
    Verifies that stream_chat yields educational mock text when key is dummy or empty.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"

    with patch.object(settings, "OPENROUTER_API_KEY", "dummy_key_for_testing"):
        chunks = list(adapter.stream_chat([{"role": "user", "content": "Hola"}]))

    full_output = "".join(chunks)
    assert "Modo demostración activo" in full_output
    assert "Estatuto Estudiantil" in full_output


def test_get_embeddings_timeout_passed():
    """
    Verifies that get_embeddings calls client.embeddings.create with timeout.
    """
    adapter = LLMAdapter()
    adapter.provider = "openrouter"

    mock_client = MagicMock()
    mock_data = MagicMock()
    mock_data.embedding = [0.1, 0.2, 0.3]
    mock_resp = MagicMock()
    mock_resp.data = [mock_data]
    mock_client.embeddings.create.return_value = mock_resp
    adapter.client = mock_client

    with patch.object(settings, "OPENROUTER_API_KEY", "sk-valid-key"):
        embeddings = adapter.get_embeddings(["Texto de prueba"])

    assert len(embeddings) == 1
    assert embeddings[0] == [0.1, 0.2, 0.3]
    call_kwargs = mock_client.embeddings.create.call_args[1]
    assert call_kwargs["timeout"] == settings.OPENROUTER_TIMEOUT


# ==============================================================================
# 11. EDGE CASE DEFENSE & REGRESSION PREVENTION TESTS
# ==============================================================================

def test_config_fallback_models_python_literal_list():
    """Verifies that OPENROUTER_FALLBACK_MODELS correctly parses Python-style single-quoted lists."""
    s = Settings(
        OPENROUTER_FALLBACK_MODELS="['meta-llama/llama-3.3-70b-instruct', 'google/gemini-2.0-flash-001']"
    )
    assert s.OPENROUTER_FALLBACK_MODELS == [
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.0-flash-001"
    ]
    # No stray brackets or single quotes in elements
    assert not any("[" in m or "]" in m or "'" in m or '"' in m for m in s.OPENROUTER_FALLBACK_MODELS)


def test_config_fallback_models_quoted_elements_comma_separated():
    """Verifies that quotes around comma-separated entries are cleanly stripped."""
    s = Settings(
        OPENROUTER_FALLBACK_MODELS='"meta-llama/llama-3.3-70b-instruct" , "google/gemini-2.0-flash-001"'
    )
    assert s.OPENROUTER_FALLBACK_MODELS == [
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.0-flash-001"
    ]


def test_is_transient_error_rejects_permanent_400_with_context_token_digits():
    """
    CRITICAL BUG TEST:
    Verifies that a 400 BadRequestError containing digits like '5000' in the message
    is NOT falsely identified as a transient 500 error.
    """
    req = httpx.Request("POST", "https://openrouter.ai")
    resp = httpx.Response(400, request=req)
    err = openai.BadRequestError("Context limit 5000 tokens exceeded", response=resp, body=None)
    assert is_transient_error(err) is False


def test_is_transient_error_rejects_permanent_4xx_codes():
    """Verifies that all standard permanent client error codes (400, 401, 403, 404, 422) return False."""
    req = httpx.Request("POST", "https://openrouter.ai")
    for status_code in [400, 401, 403, 404, 422]:
        resp = httpx.Response(status_code, request=req)
        err = openai.APIStatusError(f"HTTP {status_code}", response=resp, body=None)
        assert is_transient_error(err) is False, f"Expected status {status_code} to be non-transient"


def test_get_openrouter_models_handles_empty_or_none_primary():
    """Verifies that an empty or whitespace model_name falls back cleanly to settings."""
    adapter = LLMAdapter()
    adapter.model_name = ""
    models = adapter.get_openrouter_models()
    assert len(models) >= 1
    assert models[0] == settings.OPENROUTER_MODEL
    assert "" not in models


def test_chat_stream_does_not_cache_error_responses_in_redis():
    """
    CRITICAL DEFENSE TEST:
    Verifies that if an error chunk or interrupted connection message is emitted,
    chat.py NEVER submits the error response to Redis cache.
    """
    from app.api.v1.chat import stream_chat_response, ChatRequest
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"x-forwarded-for", b"10.0.0.88"), (b"user-agent", b"pytest-test")],
        "path": "/api/v1/chat/stream"
    }
    mock_req = Request(scope)
    mock_payload = ChatRequest(query="¿Cómo hago la monografía?", history=[])
    mock_db = MagicMock()

    # Simulate RAG service yielding an interrupted LLM stream
    def mock_answer_stream(query, history):
        yield {"type": "token", "content": "Inicio de respuesta..."}
        yield {
            "type": "token",
            "content": "\n\n*(Conexión interrumpida durante la generación de la respuesta. Por favor reintenta tu consulta.)*"
        }
        yield {"type": "citations", "citations": [{"title": "Acuerdo 038"}]}

    with patch("app.api.v1.chat.rag_service.answer_stream", side_effect=mock_answer_stream), \
         patch("app.api.v1.chat._submit_cache_write") as mock_cache_write, \
         patch("app.api.v1.chat.redis_cache.get", return_value=None):
        response = stream_chat_response(request=mock_req, payload=mock_payload, db=mock_db)
        # Consume the streaming response safely handling async generator
        if hasattr(response.body_iterator, "__anext__"):
            import anyio

            async def _consume():
                return [c async for c in response.body_iterator]

            events = anyio.run(_consume)
        else:
            events = list(response.body_iterator)
        assert len(events) > 0
        # Verify that _submit_cache_write was NOT called!
        mock_cache_write.assert_not_called()


def test_chat_stream_caches_legitimate_responses_with_academic_interruption_keywords():
    """
    CRITICAL FALSE-POSITIVE PREVENTION TEST:
    Verifies that when a legitimate academic answer explains regulations regarding
    'conexión interrumpida', 'error temporal', or 'reintenta tu consulta',
    chat.py DOES NOT falsely mark it as a stream error and DOES write to Redis cache.
    """
    from app.api.v1.chat import stream_chat_response, ChatRequest
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"x-forwarded-for", b"10.0.0.88"), (b"user-agent", b"pytest-test")],
        "path": "/api/v1/chat/stream"
    }
    mock_req = Request(scope)
    mock_payload = ChatRequest(query="¿Qué hago si se me cae el internet en un examen virtual?", history=[])
    mock_db = MagicMock()

    # Legitimate normative answer discussing connection interruptions in virtual evaluations
    def mock_answer_stream(query, history):
        yield {"type": "token", "content": "De acuerdo con el Estatuto Estudiantil, si experimentas una "}
        yield {"type": "token", "content": "conexión interrumpida durante la presentación de una evaluación virtual, "}
        yield {"type": "token", "content": "tienes derecho a solicitar una prueba supletoria ante el Consejo de Facultad. "}
        yield {"type": "token", "content": "Si ocurre un error temporal en el sistema Cóndor, reintenta tu consulta con secretaría académica."}
        yield {
            "type": "citations",
            "citations": [{"title": "Acuerdo 027 de 1993", "article": "Artículo 45", "resolution_number": "027"}]
        }

    with patch("app.api.v1.chat.rag_service.answer_stream", side_effect=mock_answer_stream), \
         patch("app.api.v1.chat._submit_cache_write") as mock_cache_write, \
         patch("app.api.v1.chat.redis_cache.get", return_value=None):
        response = stream_chat_response(request=mock_req, payload=mock_payload, db=mock_db)
        if hasattr(response.body_iterator, "__anext__"):
            import anyio

            async def _consume():
                return [c async for c in response.body_iterator]

            events = anyio.run(_consume)
        else:
            events = list(response.body_iterator)
        assert len(events) > 0
        # Verify that _submit_cache_write WAS called for this legitimate answer!
        mock_cache_write.assert_called_once()


def test_is_transient_error_string_disambiguation_for_4xx():
    """
    Verifies that generic exceptions containing '400', '401', '403', '404', '422'
    or phrases like 'bad request', 'unauthorized' are NOT classified as transient,
    even if digits like '500' appear in the message.
    """
    err1 = Exception("HTTP 400: prompt length 500 characters exceeds limit")
    assert is_transient_error(err1) is False

    err2 = Exception("401 Unauthorized: token 500 expired")
    assert is_transient_error(err2) is False

    err3 = Exception("404 Not Found: model gpt-500 does not exist")
    assert is_transient_error(err3) is False


def test_is_transient_error_cloudflare_gateway_codes():
    """
    Verifies that Cloudflare status codes (520, 521, 522, 524) common on OpenRouter
    are correctly recognized as transient retryable errors.
    """
    req = httpx.Request("POST", "https://openrouter.ai")
    for code in [520, 521, 522, 524]:
        resp = httpx.Response(code, request=req)
        err = openai.APIStatusError(f"Cloudflare {code} Gateway Timeout", response=resp, body=None)
        assert is_transient_error(err) is True, f"Expected Cloudflare status {code} to be transient"

    err_str = Exception("HTTP 524 A timeout occurred between Cloudflare and the origin web server")
    assert is_transient_error(err_str) is True


