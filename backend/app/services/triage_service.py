import os
import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.services.llm_adapter import llm_adapter
from app.services.document_processor import document_processor
from app.services.vector_store import vector_store
from app.services.normative_auditor import normative_auditor
from app.db.models import EmailNotice, DocumentItem, SystemSetting

logger = logging.getLogger(__name__)

class TriageService:
    def classify_email(
        self,
        sender: str,
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
        urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Uses LLM agent to classify if an institutional email is relevant to
        Ingeniería de Sistemas, graduation procedures, academic calendar, or faculty notices.
        """
        system_prompt = (
            "Eres el Agente Clasificador de Comunicados de la Universidad Distrital Francisco José de Caldas.\n"
            "Tu tarea es evaluar comunicados, acuerdos, resoluciones y correos institucionales para determinar si son "
            "relevantes para la base de conocimiento de estudiantes de INGENIERÍA DE SISTEMAS (Facultad de Ingeniería).\n\n"
            "ÁREAS CLAVE DE RELEVANCIA:\n"
            "1. Modalidades de Trabajo de Grado (monografía, pasantía, materias de posgrado, investigación, etc.)\n"
            "2. Reglamentación de Trabajo de Grado para pregrado (Acuerdos del Consejo Académico o Superior Universitario)\n"
            "3. Inscripción a grados, instructivos de Cóndor, fechas, paz y salvos, ceremonias o grados por ventanilla\n"
            "4. Créditos académicos, requisitos de segunda lengua (ILUD B2), derechos pecuniarios y derechos de grado\n"
            "5. Trámites y normativas ante el Consejo de Facultad de Ingeniería o Proyecto Curricular de Ingeniería de Sistemas\n\n"
            "REGLAS ESTRICTAS DE EVALUACIÓN:\n"
            "- REGLA DE ALCANCE GENERAL: Toda norma institucional de la Universidad Distrital que aplique a 'PREGRADO', "
            "'TRABAJOS DE GRADO', 'MODALIDADES DE GRADO', 'INSCRIPCIÓN DE GRADOS' o 'ESTUDIANTES DE LA UNIVERSIDAD' "
            "APLICA POR DERECHO PROPIO a los estudiantes de INGENIERÍA DE SISTEMAS. NUNCA la descartes por no mencionar "
            "textualmente 'Ingeniería de Sistemas'. Debe ser clasificada con is_relevant: true, relevance_score: entre 85.0 y 98.0, "
            "y recommended_action: 'INDEX'.\n"
            "- Solo clasifica como no relevante (is_relevant: false, relevance_score < 40.0) comunicados exclusivamente dirigidos a "
            "otras facultades (ej. artes plásticas sin alcance institucional), asuntos de pensionados, o licitaciones no académicas.\n\n"
            "Debes responder ÚNICAMENTE un objeto JSON válido con las siguientes claves exactas:\n"
            "{\n"
            '  "is_relevant": true|false,\n'
            '  "relevance_score": float entre 0.0 y 100.0,\n'
            '  "target_program": "Ingeniería de Sistemas" o programa identificado,\n'
            '  "summary": "Resumen conciso del comunicado en 2-3 oraciones",\n'
            '  "reasoning": "Explicación clara de por qué es relevante o por qué se descarta",\n'
            '  "recommended_action": "INDEX" o "IGNORE"\n'
            "}"
        )

        body_sample = body[:7500].strip() if body else ""

        user_content = (
            f"REMITENTE: {sender}\n"
            f"ASUNTO: {subject}\n"
            f"ARCHIVOS ADJUNTOS: {', '.join(attachments or ['Ninguno'])}\n"
            f"ENLACES DETECTADOS: {', '.join(urls or ['Ninguno'])}\n\n"
            f"CUERPO / TEXTO DEL DOCUMENTO:\n{body_sample}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        result = llm_adapter.generate_json(messages)

        # Guardrail: Never let core undergraduate graduation regulations be marked as irrelevant
        norm_text = (subject + " " + " ".join(attachments or []) + " " + (body[:3000] if body else "")).lower()
        core_grad_cues = [
            "modalidades de trabajo de grado",
            "modalidad de trabajo de grado",
            "reglamenta el trabajo de grado",
            "reglamentación de trabajo de grado",
            "inscripción para grados",
            "inscripción a grados",
            "ceremonias de graduación",
            "ceremonia de graduación",
            "derechos de grado"
        ]
        if any(cue in norm_text for cue in core_grad_cues):
            if not result.get("is_relevant", False) or float(result.get("relevance_score", 0.0)) < 60.0:
                logger.info("Guardrail: Correcting falsely low relevance score for core graduation notice.")
                result["is_relevant"] = True
                result["relevance_score"] = max(float(result.get("relevance_score", 0.0)), 92.0)
                result["recommended_action"] = "INDEX"
                result["target_program"] = "Ingeniería de Sistemas"
                if not result.get("summary") or "no se refiere" in result.get("reasoning", "").lower():
                    result["reasoning"] = "Reglamenta aspectos oficiales de grado para estudiantes de pregrado de la Universidad Distrital."

        return result

    def process_incoming_email(
        self,
        db: Session,
        sender: str,
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
        urls: Optional[List[str]] = None
    ) -> EmailNotice:
        """
        Processes an incoming email, runs triage classification, stores in SQLite,
        and auto-indexes if autonomous mode is enabled and classification is high confidence.
        """
        # Run classification
        triage = self.classify_email(sender, subject, body, attachments, urls)
        is_relevant = triage.get("is_relevant", False)
        score = float(triage.get("relevance_score", 0.0))

        # Check system autonomous mode and guardrails
        setting = db.query(SystemSetting).filter(SystemSetting.key == "autonomous_mode").first()
        is_autonomous = setting and setting.value.lower() == "true"

        threshold_setting = db.query(SystemSetting).filter(SystemSetting.key == "autonomous_threshold").first()
        threshold = float(threshold_setting.value) if threshold_setting and threshold_setting.value else 85.0

        ud_domain_setting = db.query(SystemSetting).filter(SystemSetting.key == "require_ud_domain").first()
        require_ud_domain = ud_domain_setting.value.lower() == "true" if ud_domain_setting and ud_domain_setting.value else True

        conflict_setting = db.query(SystemSetting).filter(SystemSetting.key == "conflict_guardrail").first()
        conflict_guardrail = conflict_setting.value.lower() == "true" if conflict_setting and conflict_setting.value else True

        is_ud_domain = sender.lower().strip().endswith("@udistrital.edu.co")
        has_conflict_keywords = any(kw in (subject + " " + body).lower() for kw in ["deroga", "derógase", "modifica acuerdo", "deja sin efecto", "sustituye"])

        # Run normative auditor to detect derogations against existing catalog
        derogation_audit = normative_auditor.audit_derogations(
            new_text=body,
            new_title=subject,
            new_date=None,
            db=db
        )

        guardrail_notes = []
        if derogation_audit.get("has_derogation"):
            conf = derogation_audit.get("confidence", 0)
            guardrail_notes.append(f"Alerta Normativa: Se detectó modificación o derogación con certeza del {conf:.0f}%.")
            for der in derogation_audit.get("derogations", []):
                guardrail_notes.append(
                    f" • {der.get('target_resolution')}: {der.get('derogation_type')} "
                    f"({', '.join(der.get('affected_articles', []))}) - {der.get('summary_of_changes')}"
                )

        if is_autonomous and is_relevant and score >= threshold:
            if require_ud_domain and not is_ud_domain:
                guardrail_notes.append("Guardrail activado: El remitente no es @udistrital.edu.co. Requiere aprobación humana.")
            if conflict_guardrail and (has_conflict_keywords or derogation_audit.get("has_derogation")):
                if derogation_audit.get("confidence", 0) < 90.0:
                    guardrail_notes.append("Guardrail activado: Conflicto normativo con certeza menor a 90%. Requiere validación de vigencia.")

            if not guardrail_notes:
                status = "AUTO_INDEXED"
            else:
                status = "PENDING_REVIEW"
        elif not is_relevant:
            status = "REJECTED"
        else:
            status = "PENDING_REVIEW"

        email_record = EmailNotice(
            sender=sender,
            subject=subject,
            body_text=body,
            has_attachments=bool(attachments),
            attachment_paths=json.dumps(attachments or []),
            extracted_urls=json.dumps(urls or []),
            is_relevant=is_relevant,
            relevance_score=score,
            triage_summary=triage.get("summary", ""),
            triage_reasoning=("\n\n".join(guardrail_notes) + "\n\n" if guardrail_notes else "") + triage.get("reasoning", ""),
            target_program=triage.get("target_program", "Ingeniería de Sistemas"),
            status=status
        )
        db.add(email_record)
        db.commit()
        db.refresh(email_record)

        # If auto-indexed, index the content now
        if status == "AUTO_INDEXED":
            self.index_email_content(db, email_record)

        return email_record

    def index_email_content(self, db: Session, email: EmailNotice) -> DocumentItem:
        """Indexes the approved email body and attachments into ChromaDB."""
        # 0. Check and apply any derogations/modifications against older regulations
        superseded_target_id = None
        try:
            audit_result = normative_auditor.audit_derogations(
                new_text=email.body_text,
                new_title=f"Comunicado: {email.subject}",
                new_date=email.received_at.strftime("%Y-%m-%d") if email.received_at else None,
                db=db
            )
            if audit_result.get("has_derogation"):
                applied = normative_auditor.apply_derogations(
                    audit_result=audit_result,
                    new_doc_title=f"Comunicado: {email.subject}",
                    db=db,
                    min_confidence=85.0
                )
                if applied:
                    superseded_target_id = applied[0].get("document_id")
        except Exception as aud_err:
            logger.warning(f"Error applying derogations during email indexing: {aud_err}")

        # 1. Index the email body as a notice document record
        doc_item = DocumentItem(
            title=f"Comunicado: {email.subject}",
            filename=f"email_{email.id}.txt",
            file_path=f"email://{email.id}",
            file_type="email_body",
            source_type="EMAIL_BODY",
            email_id=email.id,
            resolution_number=f"Comunicado Correo UD ({email.sender})",
            effective_date=email.received_at.strftime("%Y-%m-%d") if email.received_at else None,
            markdown_content=email.body_text,
            supersedes_id=superseded_target_id,
            status="INDEXED"
        )
        db.add(doc_item)
        db.commit()
        db.refresh(doc_item)

        # Check if email contains document attachments that will be indexed as canonical
        has_doc_attachments = False
        try:
            attachment_names = json.loads(email.attachment_paths or "[]")
            upload_dir = os.path.join(settings.DATA_DIR, "uploads")
            for att_name in attachment_names:
                ext = os.path.splitext(att_name)[1].lower()
                if ext in [".pdf", ".txt", ".md"] and os.path.exists(os.path.join(upload_dir, att_name)):
                    has_doc_attachments = True
                    break
        except Exception:
            pass

        # Only chunk email body into ChromaDB if there are no attached documents,
        # or if the email body is a genuine message (< 2500 chars) to prevent 70+ duplicate chunks
        if not has_doc_attachments or len(email.body_text.strip()) < 2500:
            metadata = {
                "document_id": doc_item.id,
                "title": doc_item.title,
                "filename": doc_item.filename,
                "resolution_number": doc_item.resolution_number,
                "source_type": doc_item.source_type,
                "effective_date": doc_item.effective_date or ""
            }
            chunks, metas, ids = document_processor.chunk_normative_text(email.body_text, metadata)
            if chunks:
                vector_store.add_chunks(chunks, metas, ids)
                doc_item.chunk_count = len(chunks)
                db.commit()
        else:
            doc_item.chunk_count = 0
            db.commit()

        # 2. Index any attached PDFs or documents
        try:
            attachment_names = json.loads(email.attachment_paths or "[]")
            upload_dir = os.path.join(settings.DATA_DIR, "uploads")
            for att_name in attachment_names:
                att_path = os.path.join(upload_dir, att_name)
                if os.path.exists(att_path):
                    ext = os.path.splitext(att_name)[1].lower()
                    if ext in [".pdf", ".txt", ".md"]:
                        att_text = document_processor.extract_text_from_file(att_path)
                        if att_text and len(att_text.strip()) > 50:
                            official_meta = document_processor.extract_official_metadata(att_text)
                            att_title = official_meta.get("title") or f"Adjunto: {att_name} ({email.subject})"
                            att_res_num = official_meta.get("resolution_number") or f"Adjunto de Comunicado ({email.sender})"

                            att_doc = DocumentItem(
                                title=att_title,
                                filename=att_name,
                                file_path=att_path,
                                file_type=ext.replace(".", ""),
                                source_type="EMAIL_ATTACHMENT",
                                email_id=email.id,
                                resolution_number=att_res_num,
                                effective_date=doc_item.effective_date,
                                validity_status="VIGENTE",
                                markdown_content=att_text,
                                supersedes_id=superseded_target_id,
                                status="INDEXED"
                            )
                            db.add(att_doc)
                            db.commit()
                            db.refresh(att_doc)

                            att_doc.original_pdf_url = f"/api/v1/documents/{att_doc.id}/pdf"
                            db.commit()

                            att_meta = {
                                "document_id": att_doc.id,
                                "title": att_doc.title,
                                "filename": att_doc.filename,
                                "resolution_number": att_doc.resolution_number,
                                "source_type": att_doc.source_type,
                                "effective_date": att_doc.effective_date or "",
                                "pdf_url": att_doc.original_pdf_url
                            }
                            att_chunks, att_metas, att_ids = document_processor.chunk_normative_text(att_text, att_meta)
                            if att_chunks:
                                vector_store.add_chunks(att_chunks, att_metas, att_ids)
                                att_doc.chunk_count = len(att_chunks)
                                db.commit()
                                logger.info(f"Indexed {len(att_chunks)} chunks for attached document {att_name}")
        except Exception as att_err:
            logger.warning(f"Error indexing email attachments: {att_err}")

        # Update email status
        email.status = "APPROVED_INDEXED"
        db.commit()
        return doc_item

triage_service = TriageService()

