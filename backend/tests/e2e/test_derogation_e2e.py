import os
import sys
import logging

# Ensure backend root is on sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.db.session import SessionLocal
from app.db.models import DocumentItem
from app.services.vector_store import vector_store
from app.services.document_processor import document_processor
from app.services.normative_auditor import normative_auditor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_derogation_e2e")

def test_granular_and_total_derogation_e2e():
    """
    Comprehensive End-to-End (E2E) Test Suite for Normative Derogations:
    - Phase 1: Ingests base multi-article agreement (Acuerdo 038 de 2015).
    - Phase 2: Verifies initial ChromaDB chunks and baseline RAG retrieval.
    - Phase 3: Audits new modifying agreement (Acuerdo 015 de 2026) with LLM & heuristic verification.
    - Phase 4: Applies partial derogation purging ONLY Article 12 from ChromaDB.
    - Phase 5: Asserts Article 12 is purged, Articles 1 and 18 remain in ChromaDB, and SQLite status is MODIFICADO.
    - Phase 6: Validates post-derogation RAG retrieval (new rule cited, non-derogated rules preserved).
    - Phase 7: Validates total derogation of an obsolete circular.
    """
    print("\n" + "="*80)
    print("EJECUTANDO SUITE E2E DEDICADA: tests/e2e/test_derogation_e2e.py")
    print("="*80 + "\n")

    db = SessionLocal()
    try:
        # ----------------------------------------------------------------------
        # FASE 1: CREACIÓN DE NORMA HISTÓRICA BASE (Acuerdo 038 de 2015)
        # ----------------------------------------------------------------------
        print("[FASE 1] Preparando e indexando norma base: Acuerdo 038 de 2015...")

        # Limpiar instancias previas de prueba
        existing = db.query(DocumentItem).filter(
            DocumentItem.resolution_number.in_([
                "Acuerdo 038 de 2015 (E2E)",
                "Acuerdo 015 de 2026 (E2E)",
                "Circular 002 de 2024 (E2E)",
                "Resolución 100 de 2026 (E2E)"
            ])
        ).all()
        for doc in existing:
            try:
                vector_store.delete_by_document_id(doc.id)
            except Exception:
                pass
            db.delete(doc)
        db.commit()

        # Archivar temporalmente cualquier otro Acuerdo 038 previo para garantizar aislamiento absoluto
        pre_existing_038 = db.query(DocumentItem).filter(
            DocumentItem.resolution_number.like("%038%"),
            DocumentItem.resolution_number != "Acuerdo 038 de 2015 (E2E)"
        ).all()
        for doc in pre_existing_038:
            doc.status = "ARCHIVED"
        db.commit()

        base_markdown = """# Acuerdo 038 de 2015 - Consejo Superior Universitario

### Artículo 1
Establecer el reglamento general y unificado de modalidades de grado para los estudiantes de pregrado de la Facultad de Ingeniería de la Universidad Distrital Francisco José de Caldas.

### Artículo 12
Modalidad de Pasantía: El estudiante que opte por realizar pasantía en empresa o entidad externa debe contar con un avance mínimo del 80% de créditos aprobados en su plan de estudios y un promedio ponderado acumulado no inferior a 3.2.

### Artículo 18
Modalidad de Monografía: El estudiante puede inscribir monografía de grado a partir del 70% de créditos aprobados en Ingeniería de Sistemas mediante la presentación de una propuesta de investigación avalada por un docente director ante el Comité de Currículo.
"""

        base_doc = DocumentItem(
            title="Acuerdo 038 de 2015 (Reglamento Modalidades de Grado)",
            filename="acuerdo_038_2015_e2e.md",
            file_path="/app/data/seed_documents/acuerdo_038_2015_e2e.md",
            file_type="markdown",
            source_type="SEED",
            resolution_number="Acuerdo 038 de 2015 (E2E)",
            effective_date="2015-11-20",
            validity_status="VIGENTE",
            status="INDEXED"
        )
        db.add(base_doc)
        db.commit()
        db.refresh(base_doc)

        meta_base = {
            "document_id": base_doc.id,
            "title": base_doc.title,
            "filename": base_doc.filename,
            "resolution_number": base_doc.resolution_number,
            "source_type": base_doc.source_type,
            "effective_date": base_doc.effective_date,
            "validity_status": "VIGENTE"
        }
        chunks_b, metas_b, ids_b = document_processor.chunk_normative_text(base_markdown, meta_base)
        vector_store.add_chunks(chunks_b, metas_b, ids_b)
        base_doc.chunk_count = len(chunks_b)
        db.commit()

        print(f"  ✓ Acuerdo 038 indexado con éxito (ID: {base_doc.id}, Chunks: {len(chunks_b)})")
        assert len(chunks_b) >= 3, f"Se esperaban al menos 3 chunks, se obtuvieron {len(chunks_b)}"

        initial_chunks = vector_store.get_chunks_by_document_id(base_doc.id)
        has_art12 = any("3.2" in c["content"] and "80%" in c["content"] for c in initial_chunks)
        has_art18 = any("70%" in c["content"] and "Monografía" in c["content"] for c in initial_chunks)
        assert has_art12, "El Artículo 12 (80% y 3.2) debe estar en ChromaDB"
        assert has_art18, "El Artículo 18 (70% monografía) debe estar en ChromaDB"
        print("  ✓ Chunks iniciales verificados correctamente en ChromaDB.")

        # ----------------------------------------------------------------------
        # FASE 2: VERIFICACIÓN RAG INICIAL
        # ----------------------------------------------------------------------
        print("\n[FASE 2] Verificando recuperación inicial de la norma base...")
        q_init = vector_store.query("requisito promedio creditos pasantia Acuerdo 038 de 2015", n_results=3)
        top_init = q_init[0]["content"] if q_init else ""
        print(f"  Top recuperación: {top_init[:120]}...")
        assert "3.2" in top_init or "80%" in top_init, "La recuperación inicial debe contener 3.2 / 80%"
        print("  ✓ RAG responde con la norma base histórica.")

        # ----------------------------------------------------------------------
        # FASE 3: AUDITORÍA NORMATIVA DE ACUERDO MODIFICATORIO
        # ----------------------------------------------------------------------
        print("\n[FASE 3] Evaluando Acuerdo 015 de 2026 (Derogación Parcial de Art. 12)...")
        mod_markdown = """# Acuerdo 015 de 2026 - Consejo de Facultad de Ingeniería

### Artículo 1
Modifícase expresamente el Artículo 12 del Acuerdo 038 de 2015 del Consejo Superior Universitario, el cual en adelante quedará redactado de la siguiente manera:
Artículo 12. Modalidad de Pasantía: El estudiante que opte por la modalidad de pasantía institucional o empresarial en Ingeniería de Sistemas deberá acreditar mínimo el 85% de los créditos del plan de estudios aprobados y un promedio ponderado acumulado no inferior a 3.5.

### Artículo 2
Vigencia y Derogatorias: El presente acuerdo rige a partir de la fecha de su expedición y deroga de forma expresa y exclusiva el contenido previo del Artículo 12 del Acuerdo 038 de 2015. Los demás artículos (incluidos los artículos 1 al 11 y los artículos 13 al 20) del Acuerdo 038 de 2015 continúan plenamente vigentes en su totalidad.
"""

        audit_result = normative_auditor.audit_derogations(
            new_text=mod_markdown,
            new_title="Acuerdo 015 de 2026",
            new_date="2026-03-01",
            db=db
        )

        print(f"  Resultado Auditoría: has_derogation={audit_result.get('has_derogation')}, confianza={audit_result.get('confidence')}%")
        assert audit_result.get("has_derogation") is True, "El auditor debió detectar la derogación"
        
        derogations = audit_result.get("derogations", [])
        assert len(derogations) > 0, "Debe retornar al menos una derogación estructurada"
        target_der = next((d for d in derogations if d.get("target_document_id") == base_doc.id), derogations[0])
        assert target_der.get("target_document_id") == base_doc.id, f"El documento afectado debe ser Acuerdo 038 (ID {base_doc.id}), obtenido: {target_der.get('target_document_id')}"
        assert target_der.get("derogation_type") == "PARCIAL", f"Tipo de derogación debe ser PARCIAL, obtenido: {target_der.get('derogation_type')}"
        affected = [a.lower() for a in target_der.get("affected_articles", [])]
        assert any("12" in a for a in affected), f"Debe detectar Artículo 12, detectó: {target_der.get('affected_articles')}"
        print("  ✓ Derogación PARCIAL de Artículo 12 detectada con precisión.")

        # ----------------------------------------------------------------------
        # FASE 4: EJECUCIÓN DE PURGA GRANULAR EN CHROMADB
        # ----------------------------------------------------------------------
        print("\n[FASE 4] Ejecutando purga granular en ChromaDB y registrando nueva norma...")
        applied = normative_auditor.apply_derogations(
            audit_result=audit_result,
            new_doc_title="Acuerdo 015 de 2026",
            db=db,
            min_confidence=80.0
        )
        assert len(applied) > 0, "Se debió aplicar la derogación parcial"

        # Indexar nueva norma modificatoria
        new_doc = DocumentItem(
            title="Acuerdo 015 de 2026 (Reforma Pasantías Sistemas)",
            filename="acuerdo_015_2026_e2e.md",
            file_path="/app/data/uploads/acuerdo_015_2026_e2e.md",
            file_type="markdown",
            source_type="MANUAL_UPLOAD",
            resolution_number="Acuerdo 015 de 2026 (E2E)",
            effective_date="2026-03-01",
            validity_status="VIGENTE",
            status="INDEXED"
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        meta_new = {
            "document_id": new_doc.id,
            "title": new_doc.title,
            "filename": new_doc.filename,
            "resolution_number": new_doc.resolution_number,
            "source_type": new_doc.source_type,
            "effective_date": new_doc.effective_date,
            "validity_status": "VIGENTE"
        }
        chunks_n, metas_n, ids_n = document_processor.chunk_normative_text(mod_markdown, meta_new)
        vector_store.add_chunks(chunks_n, metas_n, ids_n)
        new_doc.chunk_count = len(chunks_n)
        db.commit()
        print(f"  ✓ Acuerdo 015 de 2026 indexado con {len(chunks_n)} chunks.")

        # ----------------------------------------------------------------------
        # FASE 5: ASERCIÓN ESTRICTA EN CHROMADB Y SQLITE
        # ----------------------------------------------------------------------
        print("\n[FASE 5] Verificando rigurosidad en ChromaDB y BD...")
        db.refresh(base_doc)
        assert base_doc.validity_status == "MODIFICADO", f"Estado debió ser MODIFICADO, es: {base_doc.validity_status}"
        assert "Acuerdo 015 de 2026" in (base_doc.superseded_by_title or ""), "superseded_by_title debe vincular la reforma"

        post_chunks = vector_store.get_chunks_by_document_id(base_doc.id)
        for ch in post_chunks:
            content = ch["content"]
            assert not ("3.2" in content and "80%" in content), f"ERROR: Artículo 12 derogado sigue en ChromaDB: {content[:80]}"
        print("  ✓ CONFIRMADO: El chunk del Artículo 12 anterior fue eliminado de ChromaDB.")

        has_art1_post = any("Artículo 1" in ch["content"] or "reglamento general" in ch["content"] for ch in post_chunks)
        has_art18_post = any("70%" in ch["content"] and "Monografía" in ch["content"] for ch in post_chunks)
        assert has_art1_post, "El Artículo 1 (Vigente) fue borrado por error"
        assert has_art18_post, "El Artículo 18 (Vigente) fue borrado por error"
        print("  ✓ CONFIRMADO: Los Artículos 1 y 18 (Vigentes) se mantuvieron intactos en ChromaDB.")

        # ----------------------------------------------------------------------
        # FASE 6: VALIDACIÓN RAG POST-DEROGACIÓN
        # ----------------------------------------------------------------------
        print("\n[FASE 6] Validando respuestas RAG post-derogación...")
        res_pas = vector_store.query("nuevo requisito creditos promedio pasantia Acuerdo 015 de 2026", n_results=3)
        top_pas = res_pas[0]["content"] if res_pas else ""
        print(f"  Top Pasantías: {top_pas[:130]}...")
        assert "3.5" in top_pas or "85%" in top_pas, "Debe citar el nuevo requisito (3.5 y 85%)"
        assert not ("3.2" in top_pas and "80%" in top_pas), "No debe citar la norma derogada"
        print("  ✓ Pasantías responde con los nuevos requisitos reformados.")

        res_mono = vector_store.query("requisito monografia Acuerdo 038", n_results=3)
        top_mono = res_mono[0]["content"] if res_mono else ""
        print(f"  Top Monografía: {top_mono[:130]}...")
        assert "70%" in top_mono and "Monografía" in top_mono, "Debe seguir respondiendo con el Artículo 18 del Acuerdo 038"
        print("  ✓ Monografía sigue citando la norma base vigente.")

        # ----------------------------------------------------------------------
        # FASE 7: VALIDACIÓN DE DEROGACIÓN TOTAL
        # ----------------------------------------------------------------------
        print("\n[FASE 7] Validando Derogación Total (Circular provisional)...")
        circ_doc = DocumentItem(
            title="Circular 002 de 2024 - Calendario Provisional",
            filename="circular_002_2024_e2e.md",
            file_path="/app/data/uploads/circular_002_2024_e2e.md",
            file_type="markdown",
            source_type="MANUAL_UPLOAD",
            resolution_number="Circular 002 de 2024 (E2E)",
            effective_date="2024-02-01",
            validity_status="VIGENTE",
            status="INDEXED"
        )
        db.add(circ_doc)
        db.commit()
        db.refresh(circ_doc)

        c_chunks, c_metas, c_ids = document_processor.chunk_normative_text(
            "# Circular 002 de 2024\nFechas provisionales de sustentación: del 1 al 5 de marzo.",
            {"document_id": circ_doc.id, "title": circ_doc.title, "resolution_number": circ_doc.resolution_number}
        )
        vector_store.add_chunks(c_chunks, c_metas, c_ids)
        circ_doc.chunk_count = len(c_chunks)
        db.commit()

        total_text = "# Resolución 100 de 2026\nArtículo 1: Derógase en su totalidad la Circular 002 de 2024 sobre fechas provisionales.\n"
        audit_tot = normative_auditor.audit_derogations(total_text, "Resolución 100 de 2026", "2026-03-08", db)
        assert audit_tot.get("has_derogation") is True
        normative_auditor.apply_derogations(audit_tot, "Resolución 100 de 2026", db, min_confidence=80.0)

        db.refresh(circ_doc)
        remaining_circ = vector_store.get_chunks_by_document_id(circ_doc.id)
        assert circ_doc.validity_status == "DEROGADO"
        assert len(remaining_circ) == 0
        print("  ✓ CONFIRMADO: Derogación Total purga el 100% de los chunks de la base de conocimiento.")

        print("\n" + "="*80)
        print("RESULTADO FINAL: TODAS LAS 7 FASES DEL TEST E2E PASARON CON ÉXITO (100% APROBADO)")
        print("="*80 + "\n")

    finally:
        try:
            if 'pre_existing_038' in locals():
                for doc in pre_existing_038:
                    doc.status = "INDEXED"
                db.commit()
        except Exception:
            pass
        db.close()

if __name__ == "__main__":
    test_granular_and_total_derogation_e2e()
