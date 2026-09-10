import json
import logging
import time
from typing import List, Dict, Any, Generator, Optional
import openai
from openai import OpenAI
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

def is_transient_error(e: Exception) -> bool:
    """
    Checks if an exception is a transient error that should be retried
    with exponential backoff (e.g. 429 Too Many Requests, 502 Bad Gateway,
    503 Service Unavailable, 504 Gateway Timeout, connection reset, timeouts).
    Definitive 4xx client errors (400, 401, 403, 404, 422) are never retried.
    """
    # 1. Inspect explicit HTTP status codes
    status_code = getattr(e, "status_code", getattr(e, "code", None))
    if status_code is None and isinstance(e, httpx.HTTPStatusError) and e.response is not None:
        status_code = e.response.status_code

    if status_code is not None:
        try:
            code_int = int(status_code)
            if code_int in {429, 500, 502, 503, 504} or (520 <= code_int <= 530):
                return True
            # Permanent 4xx client errors (400, 401, 403, 404, 422) must never be retried
            if 400 <= code_int < 500:
                return False
        except (ValueError, TypeError):
            pass

    # 2. Permanent OpenAI exception classes
    if isinstance(e, (openai.AuthenticationError, openai.BadRequestError, openai.NotFoundError, openai.PermissionDeniedError)):
        return False

    # 3. Direct OpenAI exception classes for transient issues
    if isinstance(e, (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError)):
        return True

    # 4. HTTPX transport / network exceptions
    if isinstance(e, (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError, httpx.ReadError)):
        return True

    # 5. String inspection fallback: guard against permanent 4xx before checking status codes
    import re
    msg = str(e).lower()

    # If message indicates a permanent 4xx client error (and not a 429 rate limit), reject immediately
    if re.search(r"\b(400|401|403|404|422)\b", msg) and not re.search(r"\b429\b", msg):
        return False
    if any(p in msg for p in ["bad request", "unauthorized", "invalid api key", "not found", "permission denied"]):
        return False

    if re.search(r"\b(429|500|502|503|504|520|521|522|524)\b", msg):
        return True

    phrase_markers = [
        "rate limit", "too many requests", "bad gateway",
        "service unavailable", "gateway timeout", "connection error",
        "connection reset", "connection refused", "timed out",
        "read timeout", "connect timeout", "overloaded"
    ]
    if any(marker in msg for marker in phrase_markers):
        return True

    return False


def _is_repetition_loop(accumulated_text: str, min_phrase_len: int = 35, max_occurrences: int = 3) -> bool:
    """
    Detects if the LLM output has entered a degenerative repetition trap.
    Checks for:
    1. Sentences of >= 25 characters appearing >= 3 times.
    2. The recent tail (>= 35 characters) appearing >= 3 times in the entire text.
    3. Cyclical repeated suffixes (consecutive identical segments of length >= 35).
    """
    if len(accumulated_text) < 140:
        return False

    import re
    sentences = [s.strip() for s in re.split(r"[\n\.\?!]", accumulated_text) if len(s.strip()) >= 25]
    if len(sentences) >= 3:
        counts = {}
        for s in sentences:
            norm = " ".join(s.split()).lower()
            counts[norm] = counts.get(norm, 0) + 1
            if counts[norm] >= max_occurrences:
                return True

    tail = accumulated_text[-min_phrase_len:].strip()
    if len(tail) >= min_phrase_len:
        if accumulated_text.count(tail) >= max_occurrences:
            return True

    recent_window = accumulated_text[-400:]
    n = len(recent_window)
    for k in range(35, min(160, n // 2)):
        suffix = recent_window[-k:]
        prev_k = recent_window[-2 * k : -k]
        if suffix == prev_k:
            return True

    return False

class LLMAdapter:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self._init_client()

    def _init_client(self):
        if self.provider == "openrouter":
            api_key = settings.OPENROUTER_API_KEY or "dummy_key_for_testing"
            base_url = settings.OPENROUTER_BASE_URL
            self.model_name = settings.OPENROUTER_MODEL
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=settings.OPENROUTER_TIMEOUT,
                max_retries=0,
                default_headers={
                    "HTTP-Referer": "https://github.com/CanIGraduateUD",
                    "X-Title": "CanIGraduateUD-RAG"
                }
            )
        elif self.provider == "gemini":
            api_key = settings.GEMINI_API_KEY or "dummy_key"
            self.model_name = settings.GEMINI_MODEL
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                timeout=settings.OPENROUTER_TIMEOUT,
                max_retries=0
            )
        else:
            api_key = settings.OPENAI_API_KEY or "dummy_key"
            self.model_name = settings.OPENAI_MODEL
            self.client = OpenAI(
                api_key=api_key,
                timeout=settings.OPENROUTER_TIMEOUT,
                max_retries=0
            )

    def _get_api_key(self) -> str:
        if self.provider == "openrouter":
            return settings.OPENROUTER_API_KEY
        elif self.provider == "gemini":
            return settings.GEMINI_API_KEY
        return settings.OPENAI_API_KEY

    def get_openrouter_models(self) -> List[str]:
        """
        Builds the fallback models list for OpenRouter's native router:
        [primary_model, *fallback_models] preserving order and eliminating duplicates.
        """
        primary = (self.model_name or settings.OPENROUTER_MODEL or "").strip().strip("'\"")
        fallbacks = settings.OPENROUTER_FALLBACK_MODELS
        if isinstance(fallbacks, str):
            fallbacks = [m.strip().strip("'\"") for m in fallbacks.split(",") if m.strip().strip("'\"")]

        models = [primary] if primary else []
        for m in (fallbacks or []):
            clean_m = str(m).strip().strip("'\"")
            if clean_m and clean_m not in models:
                models.append(clean_m)
        return models


    def stream_chat(self, messages: List[Dict[str, str]], temperature: float = 0.25) -> Generator[str, None, None]:
        """Streams completion chunks from the selected LLM provider with OpenRouter fallback and anti-loop guardrails."""
        # Check if dummy key is present
        api_key = self._get_api_key()
        if not api_key or "your-" in api_key or "dummy" in api_key:
            # Fallback mock streaming generator for testing without configured API key
            yield "*(Aviso: Clave de API de OpenRouter no configurada en .env. Modo demostración activo)*\n\n"
            yield "De acuerdo con el **Estatuto Estudiantil (Acuerdo 027 de 1993)** y el **Acuerdo 038 de 2015 de la Facultad de Ingeniería**, los requisitos de grado para Ingeniería de Sistemas de la Universidad Distrital incluyen:\n\n"
            yield "1. **Aprobar el 100% de los créditos del pensum** con un promedio acumulado superior o igual a 3.0.\n"
            yield "2. **Aprobar una modalidad de grado** con calificación mínima de 3.5 [Acuerdo 038 de 2015, Art. 3]. Opciones: Monografía (mínimo 70% de créditos), Pasantía (mínimo 80% de créditos y promedio ≥ 3.2), o Materias de Posgrado (mínimo 85% y promedio ≥ 3.8).\n"
            yield "3. **Acreditar inglés Nivel B2** expedido o convalidado por el ILUD [Acuerdo 004 de 2021, Art. 2].\n"
            yield "4. **Paz y salvos institucionales** (Biblioteca, Laboratorios de Sistemas, Carnetización y Tesorería).\n\n"
            yield "¿Deseas información detallada sobre alguna modalidad específica como la pasantía o materias de posgrado?"
            return

        extra_kwargs: Dict[str, Any] = {
            "frequency_penalty": 0.3,
            "presence_penalty": 0.15,
        }
        if "llama" in (self.model_name or "").lower():
            extra_kwargs["stop"] = ["<|eot_id|>", "<|eom_id|>", "<|end_of_text|>", "</s>"]

        if self.provider == "openrouter":
            extra_kwargs["extra_body"] = {"models": self.get_openrouter_models()}
            extra_kwargs["timeout"] = settings.OPENROUTER_TIMEOUT

        max_retries = settings.OPENROUTER_MAX_RETRIES if self.provider == "openrouter" else 1
        backoff_factor = settings.OPENROUTER_BACKOFF_FACTOR

        tokens_emitted = 0
        for attempt in range(1, max_retries + 2):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=2048,
                    stream=True,
                    **extra_kwargs
                )
                accumulated_response = ""
                for chunk in response:
                    delta = None
                    if chunk and hasattr(chunk, "choices") and chunk.choices:
                        choice = chunk.choices[0]
                        choice_delta = getattr(choice, "delta", None)
                        if isinstance(choice_delta, dict):
                            delta = choice_delta.get("content")
                        elif choice_delta is not None:
                            delta = getattr(choice_delta, "content", None)
                    if delta:
                        accumulated_response += delta
                        if _is_repetition_loop(accumulated_response):
                            logger.warning(
                                f"[LLMAdapter] Repetition loop trap detected for model '{self.model_name}'. Safely breaking stream."
                            )
                            return
                        tokens_emitted += 1
                        yield delta
                # Stream completed successfully
                return
            except Exception as e:
                # If tokens were already emitted to the consumer, we cannot cleanly restart without duplicating text
                if tokens_emitted > 0:
                    logger.error(
                        f"[LLMAdapter] Stream interrupted mid-generation after {tokens_emitted} tokens: {e}"
                    )
                    yield f"\n\n*(Conexión interrumpida durante la generación de la respuesta. Por favor reintenta tu consulta.)*"
                    return

                # No tokens emitted yet; check if retryable transient error
                is_transient = is_transient_error(e)
                if is_transient and attempt <= max_retries:
                    delay = backoff_factor ** attempt
                    logger.warning(
                        f"[LLMAdapter] Transient error on stream attempt {attempt}/{max_retries + 1}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"[LLMAdapter] Stream failed after attempt {attempt}: {e}")
                    yield f"\n\n[Error de comunicación con el modelo LLM ({self.provider}): {str(e)}. Por favor verifica tu API Key en el archivo .env]"
                    return

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.25,
        max_tokens: int = 2048
    ) -> str:
        """Non-streaming completion with OpenRouter fallback and exponential backoff retry."""
        api_key = self._get_api_key()
        if not api_key or "your-" in api_key or "dummy" in api_key:
            return "Respuesta generada en modo demostración."

        extra_kwargs: Dict[str, Any] = {
            "frequency_penalty": 0.3,
            "presence_penalty": 0.15,
        }
        if "llama" in (self.model_name or "").lower():
            extra_kwargs["stop"] = ["<|eot_id|>", "<|eom_id|>", "<|end_of_text|>", "</s>"]

        if self.provider == "openrouter":
            extra_kwargs["extra_body"] = {"models": self.get_openrouter_models()}
            extra_kwargs["timeout"] = settings.OPENROUTER_TIMEOUT

        max_retries = settings.OPENROUTER_MAX_RETRIES if self.provider == "openrouter" else 1
        backoff_factor = settings.OPENROUTER_BACKOFF_FACTOR

        for attempt in range(1, max_retries + 2):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False,
                    **extra_kwargs
                )
                if response.choices and response.choices[0].message:
                    return response.choices[0].message.content or ""
                return ""
            except Exception as e:
                is_transient = is_transient_error(e)
                if is_transient and attempt <= max_retries:
                    delay = backoff_factor ** attempt
                    logger.warning(
                        f"[LLMAdapter] Transient error in chat_completion on attempt {attempt}/{max_retries + 1}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"[LLMAdapter] chat_completion failed after {attempt} attempts: {e}")
                    raise e

    def generate_json(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> Dict[str, Any]:
        """Generates structured JSON response (used for LLM triage of emails) with retry logic."""
        api_key = self._get_api_key()
        if not api_key or "your-" in api_key or "dummy" in api_key:
            # Smart rule-based simulation for testing without API key
            user_text = " ".join([m.get("content", "") for m in messages]).lower()
            is_relevant = any(kw in user_text for kw in ["sistemas", "grado", "grados", "pasantia", "monografia", "ilud", "comunicado", "facultad de ingenieria"])
            score = 92.0 if is_relevant else 15.0
            return {
                "is_relevant": is_relevant,
                "relevance_score": score,
                "target_program": "Ingeniería de Sistemas",
                "summary": "Comunicado oficial clasificado automáticamente por el sistema de triage." if is_relevant else "Correo informativo sin relación directa con grados o Ingeniería de Sistemas.",
                "reasoning": "Contiene palabras clave y referencias a requisitos y procedimientos de la Facultad de Ingeniería." if is_relevant else "No contiene información normativa ni de graduación.",
                "recommended_action": "INDEX" if is_relevant else "IGNORE"
            }

        extra_kwargs: Dict[str, Any] = {}
        if self.provider == "openrouter":
            extra_kwargs["extra_body"] = {"models": self.get_openrouter_models()}
            extra_kwargs["timeout"] = settings.OPENROUTER_TIMEOUT

        max_retries = settings.OPENROUTER_MAX_RETRIES if self.provider == "openrouter" else 1
        backoff_factor = settings.OPENROUTER_BACKOFF_FACTOR

        for attempt in range(1, max_retries + 2):
            try:
                try:
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=1500,
                        response_format={"type": "json_object"},
                        **extra_kwargs
                    )
                except Exception as json_mode_err:
                    if is_transient_error(json_mode_err):
                        raise json_mode_err
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=1500,
                        **extra_kwargs
                    )

                raw_choice = response.choices[0] if response.choices else None
                content = raw_choice.message.content if raw_choice and raw_choice.message else ""
                if not content:
                    content = str(getattr(raw_choice.message, "refusal", "") or "")

                clean_json = (content or "").strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0].strip()

                start_brace = clean_json.find("{")
                end_brace = clean_json.rfind("}")
                if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                    clean_json = clean_json[start_brace:end_brace + 1]

                return json.loads(clean_json)
            except Exception as e:
                is_transient = is_transient_error(e)
                if is_transient and attempt <= max_retries:
                    delay = backoff_factor ** attempt
                    logger.warning(
                        f"[LLMAdapter] Transient error in generate_json on attempt {attempt}/{max_retries + 1}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"[LLMAdapter] Error in generate_json after {attempt} attempts: {e}")
                    # Fallback parse for triage if messages contain email cues
                    user_text = " ".join([m.get("content", "") for m in messages]).lower()
                    is_relevant = any(kw in user_text for kw in ["sistemas", "grado", "grados", "pasantia", "monografia", "ilud", "comunicado"])
                    return {
                        "is_relevant": is_relevant,
                        "relevance_score": 90.0 if is_relevant else 20.0,
                        "target_program": "Ingeniería de Sistemas",
                        "summary": "Procesado con clasificación heurística de contingencia.",
                        "reasoning": f"Clasificación generada por el agente de contingencia tras agotar reintentos: {str(e)}",
                        "recommended_action": "INDEX" if is_relevant else "IGNORE"
                    }

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for vector store."""
        api_key = settings.OPENROUTER_API_KEY if self.provider == "openrouter" else settings.OPENAI_API_KEY
        if not api_key or "your-" in api_key or "dummy" in api_key:
            # Deterministic hash-based 384-dimensional embedding for testing/development
            return [self._pseudo_embedding(t, 384) for t in texts]

        try:
            # If using OpenRouter or OpenAI
            response = self.client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=texts,
                timeout=settings.OPENROUTER_TIMEOUT
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.warning(f"Failed to fetch remote embeddings ({e}), using local fallback embedding.")
            return [self._pseudo_embedding(t, 384) for t in texts]

    def _pseudo_embedding(self, text: str, dim: int = 384) -> List[float]:
        import hashlib
        import math
        import re
        import unicodedata

        common_stopwords = {
            'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un',
            'para', 'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'mas', 'pero', 'sus', 'le',
            'ya', 'o', 'este', 'si', 'porque', 'esta', 'entre', 'cuando', 'muy', 'sin', 'sobre',
            'tambien', 'me', 'hasta', 'hay', 'donde', 'quien', 'desde', 'todo', 'nos', 'durante',
            'acuerdo', 'resolucion', 'circular', 'articulo', 'art', 'csu', 'facultad', 'ingenieria',
            'universidad', 'distrital', 'francisco', 'jose', 'caldas'
        }

        vec = [0.0] * dim
        clean_text = ''.join(
            c for c in unicodedata.normalize('NFD', text.lower())
            if unicodedata.category(c) != 'Mn'
        )
        words = re.findall(r'\b\w+\b', clean_text)
        
        for word in words:
            if word in common_stopwords or len(word) <= 2:
                weight = 0.2
            elif word.isdigit():
                weight = 0.5
            else:
                weight = 3.0
            h = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16)
            vec[h % dim] += weight

        for w1, w2 in zip(words[:-1], words[1:]):
            if w1.isalpha() and w2.isalpha() and w1 not in common_stopwords and w2 not in common_stopwords:
                bigram = f'{w1}_{w2}'
                h = int(hashlib.md5(bigram.encode('utf-8')).hexdigest(), 16)
                vec[h % dim] += 2.0

        # Smooth normalization with minimum length prior (prevents tiny header snippets from dominating)
        norm = math.sqrt(sum(x * x for x in vec) + 25.0)
        return [x / norm for x in vec]

llm_adapter = LLMAdapter()

