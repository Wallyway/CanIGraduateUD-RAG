import json
import logging
from typing import List, Dict, Any, Generator
from app.services.vector_store import vector_store
from app.services.llm_adapter import llm_adapter

logger = logging.getLogger(__name__)

SYSTEM_RAG_PROMPT = """Eres el Asistente Oficial de Grados de Ingeniería de Sistemas de la Universidad Distrital Francisco José de Caldas.
Tu misión es guiar con total precisión, claridad y veracidad a los estudiantes sobre cómo graduarse, requisitos, modalidades de grado, fechas y trámites.

INSTRUCCIONES Y REGLAS ESTRICTAS DE RESPUESTA:
1. BASA TUS RESPUESTAS EXCLUSIVAMENTE EN EL CONTEXTO OFICIAL SUMINISTRADO A CONTINUACIÓN.
2. CITA SIEMPRE LA FUENTE Y EL ARTÍCULO/SECCIÓN EXACTA cuando formules una afirmación, usando el formato [Nombre del Acuerdo/Comunicado, Art. X] (por ejemplo: [Acuerdo 027 de 1993, Art. 15] o [Acuerdo 038 de 2015, Art. 8]).
3. GUARDRAIL ANTI-ALUCINACIÓN (OBLIGATORIO): Si la pregunta del estudiante NO se encuentra respondida o no hay evidencia suficiente en los fragmentos normativos suministrados, NO inventes ni supongas. Debes responder explícitamente:
   "La normativa y comunicados oficiales cargados actualmente en el sistema no registran información sobre este trámite específico. Te recomendamos consultar directamente ante la Coordinación del Proyecto Curricular de Ingeniería de Sistemas (Facultad de Ingeniería) o la Secretaría Académica."
4. ESTRUCTURA VISUAL Y ESTÉTICA DE LA RESPUESTA (OBLIGATORIO):
   - NUNCA escribas un bloque continuo o párrafos densos y amontonados de texto.
   - Divide la respuesta en secciones temáticas claras usando encabezados Markdown (### Título de Sección).
   - Escribe párrafos breves, fluidos y aireados (máximo 2 a 3 líneas por párrafo).
   - Presenta los requisitos, pasos y opciones en listas estructuradas con viñetas (-).
   - Resalta en negrita (**concepto clave**, **porcentaje de créditos**, **acuerdos**, **fechas límite**) para facilitar la lectura visual rápida.
   - Si existen notas importantes, advertencias o recomendaciones, destácalas en bloques de cita (> **Importante:** ...).
"""

class RAGService:
    def answer_stream(
        self,
        query: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Retrieves context from ChromaDB, constructs grounded prompt,
        yields text chunks and final citations for SSE streaming.
        """
        # 1. Retrieve top chunks
        results = vector_store.query(query, n_results=4)

        context_texts = []
        citations = []
        seen_sources = set()

        for res in results:
            content = res.get("content", "")
            meta = res.get("metadata", {})
            doc_title = meta.get("title", "Documento Oficial")
            res_num = meta.get("resolution_number", "")
            article = meta.get("article", "")
            
            context_texts.append(f"--- INICIO FRAGMENTO ---\n{content}\n--- FIN FRAGMENTO ---")

            citation_key = f"{doc_title}_{article}"
            if citation_key not in seen_sources:
                seen_sources.add(citation_key)
                doc_id = meta.get("document_id")
                pdf_url = meta.get("pdf_url") or (f"/api/v1/documents/{doc_id}/pdf" if doc_id else None)
                citations.append({
                    "title": doc_title,
                    "resolution": res_num,
                    "article": article,
                    "source_type": meta.get("source_type", "NORMATIVA"),
                    "excerpt": content[:250] + "..." if len(content) > 250 else content,
                    "pdf_url": pdf_url,
                    "document_id": doc_id
                })

        context_block = "\n\n".join(context_texts) if context_texts else "No se encontraron documentos en la base de datos vectorial."

        # 2. Build conversation messages
        messages = [{"role": "system", "content": SYSTEM_RAG_PROMPT}]

        # Add recent conversation history (last 4 turns)
        if conversation_history:
            for turn in conversation_history[-4:]:
                role = turn.get("role", "user")
                if role in ["user", "assistant"]:
                    messages.append({"role": role, "content": turn.get("content", "")})

        # Add current query with retrieved context
        user_prompt_with_context = (
            f"CONTEXTO OFICIAL RECUPERADO:\n{context_block}\n\n"
            f"PREGUNTA DEL ESTUDIANTE:\n{query}"
        )
        messages.append({"role": "user", "content": user_prompt_with_context})

        # 3. Stream response from LLM
        for text_chunk in llm_adapter.stream_chat(messages, temperature=0.1):
            yield {"type": "token", "content": text_chunk}

        # 4. Send citations at the end of the stream
        yield {"type": "citations", "citations": citations}

rag_service = RAGService()

