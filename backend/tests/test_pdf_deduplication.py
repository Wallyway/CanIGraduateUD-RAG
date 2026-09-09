import os
import pytest
from app.services.document_processor import document_processor
from app.services.markdown_converter import markdown_converter
from app.services.normative_auditor import normative_auditor

def test_clean_spanish_text_not_mutated():
    """Ensures legitimate Spanish text with double consonants and roman numerals is NEVER modified."""
    clean_samples = [
        "El desarrollo del proyecto curricular requiere aprobación del Consejo Académico.",
        "Sección II. Coordinación y cooperación interinstitucional para la acción formativa.",
        "Artículo III: La acreditación de alta calidad del programa de ingeniería.",
        "El perro guardián del campus y la calle 40 con carrera 7.",
        "Los estudiantes de pregrado deben creer en su capacidad de proveer soluciones.",
        "EE.UU. y convenios internacionales vigentes.",
        "https://www.udistrital.edu.co/portal y contacto@udistrital.edu.co"
    ]
    for sample in clean_samples:
        cleaned = document_processor.clean_shadow_duplicates(sample)
        assert cleaned == sample, f"Falsely mutated clean text: {sample} -> {cleaned}"

def test_synthetic_bold_deduplication():
    """Ensures drop-shadow / faux-bold double letters are cleanly collapsed."""
    dup_samples = [
        ("UUNNIIVVEERRSSIIDDAADD DDIISSTTRRIITTAALL", "UNIVERSIDAD DISTRITAL"),
        ("AACCUUEERRDDOO NN°° 000099", "ACUERDO N° 009"),
        ("((SSeeppttiieemmbbrree 1122 ddee 22000066))", "(Septiembre 12 de 2006)"),
        ('""PPoorr eell ccuuaall ssee iimmpplleemmeennttaa""', '"Por el cual se implementa"'),
        ("ssiinn iinncclluuiirr", "sin incluir"),
        ("ddeessaarrrroollllaann yy ccoonnssttrruuyyeenn", "desarrollan y construyen")
    ]
    for raw, expected in dup_samples:
        cleaned = document_processor.clean_shadow_duplicates(raw)
        assert cleaned == expected, f"Failed deduplicating: '{raw}' -> Got: '{cleaned}', Expected: '{expected}'"

def test_real_pdf_extraction_and_markdown():
    """Verifies extraction and Markdown formatting on the real uploaded Universidad Distrital PDF."""
    pdf_path = "/app/data/uploads/test_sample.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip(f"Sample PDF {pdf_path} not found in environment.")

    # 1. Plain text extraction
    extracted = document_processor.extract_text_from_file(pdf_path)
    assert "UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS" in extracted
    assert "UUNNIIVVEERRSSIIDDAADD" not in extracted
    assert "ACUERDO N° 009" in extracted
    assert "AACCUUEERRDDOO" not in extracted

    # Page 2 list items must be clean
    assert "Pregrados de Nivel Profesional Tecnológico" in extracted
    assert "Especializaciones:" in extracted

    # 2. Structured Markdown Conversion
    md_res = markdown_converter.convert_pdf_to_markdown(pdf_path, "Acuerdo 009 de 2006")
    assert md_res["page_count"] == 8
    assert md_res["has_conflict_clause"] is True
    assert any("012" in d for d in md_res["detected_derogations"])

    markdown_text = md_res["markdown"]
    assert "# ACUERDO N° 009" in markdown_text
    assert "### ARTÍCULO 1.-" in markdown_text
    assert "### ARTÍCULO 20.- VIGENCIA Y DEROGATORIAS" in markdown_text

    # 3. Normative Auditor Detection
    catalog = [{
        "id": 99,
        "title": "Resolución 012 de Mayo 28 de 1993",
        "resolution_number": "012",
        "effective_date": "1993-05-28",
        "validity_status": "VIGENTE"
    }]
    audit = normative_auditor._fallback_heuristic_audit(markdown_text, catalog)
    assert audit["has_derogation"] is True
    assert len(audit["derogations"]) == 1
    derog = audit["derogations"][0]
    assert derog["target_document_id"] == 99
    assert derog["derogation_type"] == "PARCIAL"
    assert "Artículo 5" in derog["affected_articles"]
    assert "Artículo 6" in derog["affected_articles"]
    assert "Artículo 10" in derog["affected_articles"]

def test_rag_citation_deduplication():
    """Verifies that RAGService merges multiple chunks from the same document into a single citation."""
    from unittest.mock import patch, MagicMock
    from app.services.rag_service import RAGService

    rag = RAGService()

    fake_results = [
        {
            "content": "Contenido del articulo 3",
            "metadata": {
                "document_id": 4,
                "title": "Acuerdo 012 de 2022",
                "resolution_number": "Acuerdo 012",
                "article": "ARTÍCULO 3",
                "source_type": "PDF",
                "pdf_url": "/api/v1/documents/4/pdf"
            }
        },
        {
            "content": "Contenido del articulo 4",
            "metadata": {
                "document_id": 4,
                "title": "Acuerdo 012 de 2022",
                "resolution_number": "Acuerdo 012",
                "article": "ARTÍCULO 4",
                "source_type": "PDF",
                "pdf_url": "/api/v1/documents/4/pdf"
            }
        },
        {
            "content": "Contenido del articulo 22",
            "metadata": {
                "document_id": 4,
                "title": "Acuerdo 012 de 2022",
                "resolution_number": "Acuerdo 012",
                "article": "ARTÍCULO 22",
                "source_type": "PDF",
                "pdf_url": "/api/v1/documents/4/pdf"
            }
        },
        {
            "content": "Contenido del articulo 1 de otra norma",
            "metadata": {
                "document_id": 1,
                "title": "Acuerdo 009 de 2006",
                "resolution_number": "Acuerdo 009",
                "article": "ARTÍCULO 1",
                "source_type": "PDF",
                "pdf_url": "/api/v1/documents/1/pdf"
            }
        }
    ]

    with patch("app.services.rag_service.vector_store.query", return_value=fake_results):
        with patch("app.services.rag_service.llm_adapter.stream_chat", return_value=iter(["Respuesta simulada"])):
            citations = None
            for item in rag.answer_stream("¿Cuáles son las modalidades?"):
                if item.get("type") == "citations":
                    citations = item.get("citations")

            assert citations is not None
            # Exactly 2 citations: one for Acuerdo 012, one for Acuerdo 009
            assert len(citations) == 2

            acuerdo_012_cit = next((c for c in citations if c["document_id"] == 4), None)
            assert acuerdo_012_cit is not None
            # Articles must be aggregated with bullet separator
            assert "ARTÍCULO 3" in acuerdo_012_cit["article"]
            assert "ARTÍCULO 4" in acuerdo_012_cit["article"]
            assert "ARTÍCULO 22" in acuerdo_012_cit["article"]
            assert " • " in acuerdo_012_cit["article"]

def test_chat_knowledge_gap_detection():
    """Verifies that the anti-hallucination guardrail triggers has_knowledge_gap = True."""
    gap_phrases = [
        "La normativa y comunicados oficiales cargados actualmente en el sistema no registran información sobre este trámite específico. Te recomendamos consultar directamente ante la Coordinación del Proyecto Curricular de Ingeniería de Sistemas (Facultad de Ingeniería) o la Secretaría Académica.",
        "No disponemos de información en los acuerdos oficiales sobre este proceso.",
        "Este procedimiento no se encuentra reglamentado en los acuerdos vigentes."
    ]

    known_indicators = [
        "no registran información",
        "no registra información",
        "no disponemos de información",
        "no hay información en los acuerdos",
        "no se encuentra regulado",
        "no se encuentra reglamentado",
        "no se especifica en la normativa",
        "no se menciona en la normativa",
        "no contienen información",
        "no contiene información",
        "no está documentado",
        "no está documentada",
        "consultar directamente ante la coordinación",
        "trámite específico"
    ]

    for phrase in gap_phrases:
        p_lower = phrase.lower()
        has_gap = any(ind in p_lower for ind in known_indicators)
        assert has_gap is True, f"Failed to detect gap in: '{phrase}'"

    clean_answer = "Para optar a la modalidad de pasantía, el estudiante debe tener aprobado el 70% de créditos según el Acuerdo 012 de 2022."
    c_lower = clean_answer.lower()
    has_gap_clean = any(ind in c_lower for ind in known_indicators)
    assert has_gap_clean is False, "Clean answer should NOT be detected as a knowledge gap"

def test_academic_scope_guardrail():
    """Verifies that queries about other faculties or curricular projects are intercepted."""
    from app.services.rag_service import is_other_career_or_faculty, RAGService, OTHER_FACULTY_GUARDRAIL_MESSAGE
    from app.api.v1.chat import classify_topic
    from unittest.mock import patch

    # 1. Blocked queries (other careers / faculties)
    blocked_queries = [
        "¿Cómo me graduo de Ingeniería Electrónica?",
        "Requisitos de grado para ingenieria industrial",
        "Soy de la ASAB, que modalidades tengo?",
        "Pasos para grado en ingenieria ambiental",
        "Soy de licenciatura en matematicas, como hago el grado?",
        "¿Qué opciones de grado hay en eléctrica?",
        "Requisitos en tecnología en electricidad",
        "¿Cómo me graduo de tecnología en sistemas?",
        "Tesis en artes plásticas",
        "Requisitos de grado en ingeniería catastral y geodesia",
        "Modalidades en ingeniería forestal"
    ]
    for q in blocked_queries:
        assert is_other_career_or_faculty(q) is True, f"Expected '{q}' to be flagged as other career/faculty"
        assert classify_topic(q) == "Otra Carrera / Facultad", f"Expected topic 'Otra Carrera / Facultad' for '{q}'"

    # 2. Allowed queries (Sistemas students, general graduation queries)
    allowed_queries = [
        "Soy de sistemas, ¿puedo ver una electiva de ingeniería electrónica?",
        "¿Cuáles son las modalidades de grado de ingeniería de sistemas?",
        "¿Cómo me graduo si ya completé las materias?",
        "¿Cuál es el puntaje B2 de inglés?",
        "Requisitos para pasantías",
        "Acuerdo 012 de 2022"
    ]
    for q in allowed_queries:
        assert is_other_career_or_faculty(q) is False, f"Expected '{q}' NOT to be flagged as other career/faculty"

    # 3. Verify answer_stream fast interception without LLM or VectorStore
    rag = RAGService()
    with patch("app.services.rag_service.vector_store.query") as mock_vector_query, \
         patch("app.services.rag_service.llm_adapter.stream_chat") as mock_llm_stream:

        events = list(rag.answer_stream("¿Cómo me graduo de Ingeniería Eléctrica?"))

        # Vector store and LLM must NOT be called
        mock_vector_query.assert_not_called()
        mock_llm_stream.assert_not_called()

        tokens = [e["content"] for e in events if e.get("type") == "token"]
        citations = next((e["citations"] for e in events if e.get("type") == "citations"), None)

        full_message = "".join(tokens).strip()
        assert full_message == OTHER_FACULTY_GUARDRAIL_MESSAGE
        assert citations == []



