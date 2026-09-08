import json
import logging
from typing import List, Dict, Any, Generator, Optional
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

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
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
        else:
            api_key = settings.OPENAI_API_KEY or "dummy_key"
            self.model_name = settings.OPENAI_MODEL
            self.client = OpenAI(api_key=api_key)

    def stream_chat(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> Generator[str, None, None]:
        """Streams completion chunks from the selected LLM provider."""
        # Check if dummy key is present
        api_key = settings.OPENROUTER_API_KEY if self.provider == "openrouter" else settings.OPENAI_API_KEY
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

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=2048,
                stream=True
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Error calling LLM stream: {e}")
            yield f"\n\n[Error de comunicación con el modelo LLM ({self.provider}): {str(e)}. Por favor verifica tu API Key en el archivo .env]"

    def generate_json(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> Dict[str, Any]:
        """Generates structured JSON response (used for LLM triage of emails)."""
        api_key = settings.OPENROUTER_API_KEY if self.provider == "openrouter" else settings.OPENAI_API_KEY
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

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"Error in generate_json: {e}")
            # Fallback parse
            return {
                "is_relevant": True,
                "relevance_score": 75.0,
                "target_program": "Ingeniería de Sistemas",
                "summary": "Procesado con clasificación de respaldo.",
                "reasoning": f"Clasificación heurística debido a: {str(e)}",
                "recommended_action": "INDEX"
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
                input=texts
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.warning(f"Failed to fetch remote embeddings ({e}), using local fallback embedding.")
            return [self._pseudo_embedding(t, 384) for t in texts]

    def _pseudo_embedding(self, text: str, dim: int = 384) -> List[float]:
        import hashlib
        import math
        vec = [0.0] * dim
        for i, word in enumerate(text.lower().split()):
            h = int(hashlib.md5(f"{word}_{i % 10}".encode('utf-8')).hexdigest(), 16)
            pos = h % dim
            vec[pos] += 1.0
        # Normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

llm_adapter = LLMAdapter()

