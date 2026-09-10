import json
import re
import logging
from typing import List, Dict, Any, Generator, Optional
from app.services.vector_store import vector_store
from app.services.llm_adapter import llm_adapter

logger = logging.getLogger(__name__)

OTHER_FACULTY_GUARDRAIL_MESSAGE = (
    "Por ahora estamos probando nuestra herramienta en Ingeniería de Sistemas. "
    "Esperamos poder llegar a tu facultad y ser tu guía en el proceso de graduarte 🎓✨"
)

# Pattern for other careers/faculties at Universidad Distrital
OTHER_PROGRAM_PATTERNS = [
    # Ingenierías diferentes a Sistemas
    r"\b(?:ingenier[ií]a|ing\.?)\s+(?:electr[oó]nica|el[eé]ctrica|industrial|catastral|mec[aá]nica|civil|telecomunicaciones|control|qu[ií]mica)\b",
    r"\b(?:electr[oó]nica|el[eé]ctrica|catastral|geodesia)\b",
    r"\b(?:de|en|para|soy de|estudio)\s+industrial\b",
    
    # Facultad de Medio Ambiente y Recursos Naturales
    r"\b(?:ingenier[ií]a|ing\.?|administraci[oó]n)\s+(?:ambiental|forestal|sanitaria|topogr[aá]fica)\b",
    r"\b(?:forestal|sanitaria|topogr[aá]fica)\b",
    r"\b(?:de|en|para|soy de|estudio)\s+ambiental\b",
    r"\bfacultad\s+(?:del?\s+)?medio\s+ambiente\b",
    
    # Facultad de Ciencias y Educación
    r"\blicenciatura[s]?\b",
    r"\b(?:licenciatura\s+en\s+)?(?:matem[aá]ticas|f[ií]sica|qu[ií]mica|biolog[ií]a|ciencias\s+sociales|educaci[oó]n\s+infantil|educaci[oó]n\s+b[aá]sica|lenguas)\b",
    r"\bfacultad\s+(?:de\s+)?ciencias\s+y\s+educaci[oó]n\b",
    
    # Facultad de Artes (ASAB)
    r"\basab\b",
    r"\b(?:artes\s+pl[aá]sticas|arte\s+dram[aá]tico|artes?\s+danzarias?|danza|artes?\s+musicales?|m[uú]sica)\b",
    r"\bfacultad\s+(?:de\s+)?artes\b",
    
    # Facultad Tecnológica
    r"\bfacultad\s+tecnol[oó]gica\b",
    r"\btecnolog[ií]a\s+(?:en|de)\s+(?:electr[oó]nica|electricidad|mec[aá]nica|industrial|sistemas|construcci[oó]n|gesti[oó]n)\b",
    r"\b(?:tecn[oó]logo|tecn[oó]loga|tecnol[oó]gico)\b"
]

def is_other_career_or_faculty(query: str) -> bool:
    """
    Detects if the query targets a curricular project or faculty other than
    Ingeniería de Sistemas at Universidad Distrital.
    
    Safe pass: If the user explicitly mentions being in / asking from the perspective
    of 'sistemas' (e.g. cross-curricular electives or postgraduate subjects), returns False.
    """
    if not query:
        return False
        
    q = query.lower()
    
    # Safe pass check: if user mentions 'sistemas', do not block via fast regex
    # (Allow RAG to address cross-faculty queries if relevant, or prompt guardrail to decide)
    if "sistemas" in q:
        # Special case: if query is explicitly asking about "tecnología en sistemas" (Facultad Tecnológica),
        # that is NOT Ingeniería de Sistemas (Facultad de Ingeniería).
        if re.search(r"\btecnolog[ií]a\s+(?:en\s+)?sistemas\b", q) and not re.search(r"\bingenier[ií]a\s+(?:de\s+)?sistemas\b", q):
            return True
        return False
        
    for pattern in OTHER_PROGRAM_PATTERNS:
        if re.search(pattern, q, re.IGNORECASE):
            return True
            
    return False

def detect_other_career(query: str) -> Optional[str]:
    """
    Identifies which specific career or faculty is mentioned in an out-of-scope query.
    Returns a standardized career/faculty name for analytics and demand tracking.
    """
    if not query:
        return None
    q = query.lower()

    if re.search(r"\b(?:electr[oó]nica)\b", q):
        return "Ingeniería Electrónica"
    elif re.search(r"\b(?:el[eé]ctrica)\b", q):
        return "Ingeniería Eléctrica"
    elif re.search(r"\b(?:industrial)\b", q):
        return "Ingeniería Industrial"
    elif re.search(r"\b(?:catastral|geodesia)\b", q):
        return "Ingeniería Catastral y Geodesia"
    elif re.search(r"\b(?:mec[aá]nica)\b", q):
        return "Ingeniería Mecánica"
    elif re.search(r"\b(?:civil)\b", q):
        return "Ingeniería Civil"
    elif re.search(r"\b(?:ambiental|forestal|sanitaria|topogr[aá]fica|medio\s+ambiente)\b", q):
        if "ambiental" in q:
            return "Ingeniería Ambiental"
        elif "forestal" in q:
            return "Ingeniería Forestal"
        elif "sanitaria" in q:
            return "Ingeniería Sanitaria"
        elif "topogr" in q:
            return "Ingeniería Topográfica"
        return "Facultad del Medio Ambiente"
    elif re.search(r"\b(?:licenciatura|ciencias\s+y\s+educaci|matem[aá]ticas|f[ií]sica|qu[ií]mica|biolog[ií]a)\b", q):
        return "Licenciaturas (Ciencias y Educación)"
    elif re.search(r"\b(?:asab|artes|dram[aá]tico|danza|m[uú]sica)\b", q):
        return "Facultad de Artes (ASAB)"
    elif re.search(r"\b(?:tecnol[oó]gic|tecnolog[ií]a)\b", q):
        return "Facultad Tecnológica"
    elif is_other_career_or_faculty(query):
        return "Otra Carrera / Facultad"
    return None

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
5. GUARDRAIL DE ALCANCE ACADÉMICO (OTRAS CARRERAS Y FACULTADES):
   Esta plataforma está especializada y en fase de pruebas exclusivamente para el Proyecto Curricular de Ingeniería de Sistemas (Facultad de Ingeniería).
   Si el estudiante formula preguntas sobre requisitos, trámites, pasantías o modalidades de grado de OTRA carrera, facultad o proyecto curricular (por ejemplo: Ingeniería Electrónica, Eléctrica, Industrial, Catastral, Ambiental, Forestal, Licenciaturas, Artes/ASAB, Tecnologías, etc.) y NO aclara ser estudiante de Ingeniería de Sistemas consultando por materias o convenios interfacultades, DEBES responder exactamente:
   "Por ahora estamos probando nuestra herramienta en Ingeniería de Sistemas. Esperamos poder llegar a tu facultad y ser tu guía en el proceso de graduarte 🎓✨"
"""

class RAGService:
    def answer_stream(
        self,
        query: str,
        conversation_history: List[Dict[str, str]] = None,
        emit_heartbeat: bool = False
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Retrieves context from ChromaDB, constructs grounded prompt,
        yields text chunks and final citations for SSE streaming.
        Intercepts other careers/faculties with friendly scope message.
        """
        # Fast guardrail: check if asking about another career/faculty
        if is_other_career_or_faculty(query):
            # Stream friendly message in smooth token chunks
            words = OTHER_FACULTY_GUARDRAIL_MESSAGE.split(" ")
            for i, word in enumerate(words):
                chunk = word if i == len(words) - 1 else word + " "
                yield {"type": "token", "content": chunk}
            yield {"type": "citations", "citations": []}
            return

        # Emit initial keepalive ping before vector store retrieval if requested
        if emit_heartbeat:
            yield {"type": "ping"}

        # 1. Retrieve top chunks
        results = vector_store.query(query, n_results=6)

        # Deduplicate and aggregate citations strictly by document (document_id or title)
        context_texts = []
        doc_citations = {}

        for res in results:
            content = res.get("content", "")
            meta = res.get("metadata", {})
            doc_title = meta.get("title", "Documento Oficial")
            res_num = meta.get("resolution_number", "")
            article = meta.get("article", "")
            doc_id = meta.get("document_id")
            pdf_url = meta.get("pdf_url") or (f"/api/v1/documents/{doc_id}/pdf" if doc_id else None)
            
            context_texts.append(f"--- INICIO FRAGMENTO ---\n{content}\n--- FIN FRAGMENTO ---")

            doc_key = str(doc_id) if doc_id else doc_title.strip().lower()
            if doc_key not in doc_citations:
                doc_citations[doc_key] = {
                    "title": doc_title,
                    "resolution": res_num,
                    "articles": [article] if article else [],
                    "source_type": meta.get("source_type", "NORMATIVA"),
                    "excerpt": content[:250] + "..." if len(content) > 250 else content,
                    "pdf_url": pdf_url,
                    "document_id": doc_id
                }
            else:
                if article and article not in doc_citations[doc_key]["articles"]:
                    doc_citations[doc_key]["articles"].append(article)

        citations = []
        for item in doc_citations.values():
            articles_list = item.pop("articles", [])
            item["article"] = " • ".join(articles_list) if articles_list else ""
            citations.append(item)

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

        # 3. Stream response from LLM with mid-stream resilience
        if emit_heartbeat:
            yield {"type": "ping"}

        try:
            for text_chunk in llm_adapter.stream_chat(messages, temperature=0.25):
                yield {"type": "token", "content": text_chunk}
        except Exception as stream_err:
            logger.error(f"[RAGService] Exception during LLM stream consumption: {stream_err}")
            yield {
                "type": "token",
                "content": f"\n\n*(Error temporal durante la generación de la respuesta: {str(stream_err)})*",
                "is_error": True
            }

        # 4. Send citations at the end of the stream (guaranteed delivery)
        yield {"type": "citations", "citations": citations}

    def embed_query(self, query: str) -> List[float]:
        """Generates embedding vector for a query using the configured embedding provider."""
        embeddings = llm_adapter.get_embeddings([query])
        return embeddings[0] if embeddings else []

rag_service = RAGService()

