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
