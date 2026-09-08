import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.services.llm_adapter import llm_adapter
from app.services.document_processor import document_processor
from app.services.vector_store import vector_store
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
            "Tu tarea es evaluar correos electrónicos recibidos en la cuenta institucional y determinar si son "
            "relevantes para estudiantes de INGENIERÍA DE SISTEMAS respecto a:\n"
            "- Modalidades y opciones de grado (monografía, pasantía, materias de posgrado, etc.)\n"
            "- Calendario académico, fechas de grado, grados por ventanilla o ceremonias\n"
            "- Paz y salvos, ILUD (inglés B2), o trámites ante el Consejo de Facultad / Proyecto Curricular\n"
            "- Convocatorias oficiales de la Facultad de Ingeniería\n\n"
            "Debes responder ÚNICAMENTE un objeto JSON válido con las siguientes claves exactas:\n"
            "{\n"
            '  "is_relevant": true|false,\n'
            '  "relevance_score": float entre 0.0 y 100.0,\n'
            '  "target_program": "Ingeniería de Sistemas" o programa identificado,\n'
            '  "summary": "Resumen conciso del comunicado en 2-3 oraciones",\n'
            '  "reasoning": "Explicación breve de por qué es relevante o por qué se descarta",\n'
            '  "recommended_action": "INDEX" o "IGNORE"\n'
            "}"
        )

        user_content = (
            f"REMITENTE: {sender}\n"
            f"ASUNTO: {subject}\n"
            f"ARCHIVOS ADJUNTOS: {', '.join(attachments or ['Ninguno'])}\n"
            f"ENLACES DETECTADOS: {', '.join(urls or ['Ninguno'])}\n\n"
            f"CUERPO DEL CORREO:\n{body[:3000]}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        result = llm_adapter.generate_json(messages)
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

        guardrail_notes = []
        if is_autonomous and is_relevant and score >= threshold:
            if require_ud_domain and not is_ud_domain:
                guardrail_notes.append("Guardrail activado: El remitente no es @udistrital.edu.co. Requiere aprobación humana.")
            if conflict_guardrail and has_conflict_keywords:
                guardrail_notes.append("Guardrail activado: Se detectó una cláusula de posible derogación o modificación normativa. Requiere validación de vigencia.")

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
        # 1. Index the email body as a notice document
        doc_item = DocumentItem(
            title=f"Comunicado: {email.subject}",
            filename=f"email_{email.id}.txt",
            file_path=f"email://{email.id}",
            file_type="email_body",
            source_type="EMAIL_BODY",
            email_id=email.id,
            resolution_number=f"Comunicado Correo UD ({email.sender})",
            effective_date=email.received_at.strftime("%Y-%m-%d"),
            status="INDEXED"
        )
        db.add(doc_item)
        db.commit()
        db.refresh(doc_item)

        # Chunk and upsert into Chroma
        metadata = {
            "document_id": doc_item.id,
            "title": doc_item.title,
            "filename": doc_item.filename,
            "resolution_number": doc_item.resolution_number,
            "source_type": doc_item.source_type,
            "effective_date": doc_item.effective_date
        }
        chunks, metas, ids = document_processor.chunk_normative_text(email.body_text, metadata)
        if chunks:
            vector_store.add_chunks(chunks, metas, ids)
            doc_item.chunk_count = len(chunks)
            db.commit()

        # Update email status
        email.status = "APPROVED_INDEXED"
        db.commit()
        return doc_item

triage_service = TriageService()

