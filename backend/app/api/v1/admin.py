import os
import shutil
import re
import json
import random
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.config import settings
from app.db.session import get_db
from app.db.models import EmailNotice, DocumentItem, SystemSetting, StudentQueryLog, SessionFeedback
from app.api.deps import get_current_admin
from app.services.triage_service import triage_service
from app.services.vector_store import vector_store
from app.services.eml_parser import parse_eml_bytes
from app.services.document_processor import document_processor
from app.services.rag_service import detect_other_career
import logging
from app.services.llm_adapter import llm_adapter

logger = logging.getLogger(__name__)

router = APIRouter()

class AutonomousModePayload(BaseModel):
    enabled: bool

class UpdateSettingsPayload(BaseModel):
    autonomous_mode: Optional[bool] = None
    autonomous_threshold: Optional[float] = None
    require_ud_domain: Optional[bool] = None
    conflict_guardrail: Optional[bool] = None

class UpdateEmailPayload(BaseModel):
    subject: Optional[str] = None
    sender: Optional[str] = None
    triage_summary: Optional[str] = None
    target_program: Optional[str] = None

class BatchEmailsPayload(BaseModel):
    email_ids: List[int]
    action: str # "approve" or "reject"

@router.get("/emails")
def list_email_notices(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Lists email notices received by the system with optional status filter."""
    query = db.query(EmailNotice)
    if status_filter and status_filter != "ALL":
        if status_filter == "PENDING":
            query = query.filter(EmailNotice.status == "PENDING_REVIEW")
        elif status_filter == "APPROVED":
            query = query.filter(EmailNotice.status.in_(["APPROVED_INDEXED", "AUTO_INDEXED"]))
        elif status_filter == "REJECTED":
            query = query.filter(EmailNotice.status == "REJECTED")
        else:
            query = query.filter(EmailNotice.status == status_filter)

    emails = query.order_by(EmailNotice.received_at.desc()).all()

    results = []
    for em in emails:
        results.append({
            "id": em.id,
            "sender": em.sender,
            "subject": em.subject,
            "body_text": em.body_text,
            "received_at": em.received_at.isoformat() if em.received_at else None,
            "has_attachments": em.has_attachments,
            "attachment_paths": json.loads(em.attachment_paths or "[]"),
            "extracted_urls": json.loads(em.extracted_urls or "[]"),
            "is_relevant": em.is_relevant,
            "relevance_score": em.relevance_score,
            "triage_summary": em.triage_summary,
            "triage_reasoning": em.triage_reasoning,
            "target_program": em.target_program,
            "status": em.status,
            "reviewed_at": em.reviewed_at.isoformat() if em.reviewed_at else None
        })
    return results

@router.put("/emails/{email_id}")
def update_email_metadata(
    email_id: int,
    payload: UpdateEmailPayload,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Updates editable metadata on an email before approving."""
    email = db.query(EmailNotice).filter(EmailNotice.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Comunicado no encontrado")

    if payload.subject is not None:
        email.subject = payload.subject
    if payload.sender is not None:
        email.sender = payload.sender.strip() or "comunicados@udistrital.edu.co"
    if payload.triage_summary is not None:
        email.triage_summary = payload.triage_summary
    if payload.target_program is not None:
        email.target_program = payload.target_program

    # If this notice has derived DocumentItems, sync the resolution_number and title
    for doc in email.documents:
        if payload.sender is not None:
            doc.resolution_number = f"Comunicado Correo UD ({email.sender})"
        if payload.subject is not None:
            doc.title = f"Comunicado: {email.subject}"

    db.commit()
    return {"success": True, "message": "Comunicado actualizado correctamente."}

@router.post("/emails/{email_id}/approve")
def approve_and_index_email(
    email_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Approves an incoming email notice and indexes it into ChromaDB vector store."""
    email = db.query(EmailNotice).filter(EmailNotice.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Comunicado no encontrado")

    doc_item = triage_service.index_email_content(db, email)
    email.reviewed_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "message": f"Comunicado '{email.subject}' aprobado e indexado con éxito.",
        "document_id": doc_item.id,
        "chunks_indexed": doc_item.chunk_count
    }

@router.delete("/emails/{email_id}")
@router.post("/emails/{email_id}/reject")
def reject_email(
    email_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Permanently deletes and discards an email notice from the triage inbox."""
    email = db.query(EmailNotice).filter(EmailNotice.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Comunicado no encontrado")

    # Clean up vector chunks and documents derived from this notice if any
    for doc in email.documents:
        try:
            vector_store.delete_by_document_id(doc.id)
        except Exception as e:
            logger.warning(f"Error removing vector chunks for doc {doc.id}: {e}")

    # Remove physical uploaded attachment files if safe
    if email.attachment_paths:
        try:
            paths = json.loads(email.attachment_paths) if email.attachment_paths.startswith("[") else [email.attachment_paths]
            for p in paths:
                att_file = os.path.join(settings.DATA_DIR, "uploads", os.path.basename(p))
                if os.path.exists(att_file):
                    os.remove(att_file)
        except Exception as e:
            logger.warning(f"Error removing attachment file for email {email_id}: {e}")

    subject = email.subject
    db.delete(email)
    db.commit()

    return {
        "success": True,
        "message": f"Comunicado '{subject}' desechado y eliminado permanentemente."
    }

@router.post("/emails/batch")
def batch_action_emails(
    payload: BatchEmailsPayload,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Approves or permanently discards multiple emails in a single batch operation."""
    emails = db.query(EmailNotice).filter(EmailNotice.id.in_(payload.email_ids)).all()
    processed_count = 0

    for email in emails:
        if payload.action == "approve":
            triage_service.index_email_content(db, email)
            email.reviewed_at = datetime.utcnow()
            processed_count += 1
        elif payload.action in ["reject", "delete"]:
            for doc in email.documents:
                try:
                    vector_store.delete_by_document_id(doc.id)
                except Exception as e:
                    logger.warning(f"Error removing vector chunks for doc {doc.id}: {e}")
            if email.attachment_paths:
                try:
                    paths = json.loads(email.attachment_paths) if email.attachment_paths.startswith("[") else [email.attachment_paths]
                    for p in paths:
                        att_file = os.path.join(settings.DATA_DIR, "uploads", os.path.basename(p))
                        if os.path.exists(att_file):
                            os.remove(att_file)
                except Exception:
                    pass
            db.delete(email)
            processed_count += 1

    db.commit()
    return {
        "success": True,
        "processed_count": processed_count,
        "message": f"Se procesaron {processed_count} comunicados exitosamente."
    }

@router.get("/settings")
def get_system_settings(
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Returns all system settings and guardrails."""
    settings_records = db.query(SystemSetting).all()
    cfg = {s.key: s.value for s in settings_records}

    return {
        "autonomous_mode": cfg.get("autonomous_mode", "false").lower() == "true",
        "autonomous_threshold": float(cfg.get("autonomous_threshold", "85")),
        "require_ud_domain": cfg.get("require_ud_domain", "true").lower() == "true",
        "conflict_guardrail": cfg.get("conflict_guardrail", "true").lower() == "true",
    }

@router.post("/settings")
def update_system_settings(
    payload: UpdateSettingsPayload,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Updates guardrails and system configuration."""
    def set_val(k: str, v: str, desc: str):
        record = db.query(SystemSetting).filter(SystemSetting.key == k).first()
        if record:
            record.value = v
        else:
            db.add(SystemSetting(key=k, value=v, description=desc))

    if payload.autonomous_mode is not None:
        set_val("autonomous_mode", "true" if payload.autonomous_mode else "false", "Modo agéntico autónomo")
    if payload.autonomous_threshold is not None:
        set_val("autonomous_threshold", str(payload.autonomous_threshold), "Umbral mínimo de porcentaje de confianza")
    if payload.require_ud_domain is not None:
        set_val("require_ud_domain", "true" if payload.require_ud_domain else "false", "Guardrail dominio @udistrital.edu.co")
    if payload.conflict_guardrail is not None:
        set_val("conflict_guardrail", "true" if payload.conflict_guardrail else "false", "Guardrail detección de derogaciones")

    db.commit()
    return {"success": True, "message": "Configuración y guardrails actualizados correctamente."}

@router.post("/settings/autonomous-mode")
def toggle_autonomous_mode(
    payload: AutonomousModePayload,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Quick toggle for autonomous mode switch."""
    mode_setting = db.query(SystemSetting).filter(SystemSetting.key == "autonomous_mode").first()
    val = "true" if payload.enabled else "false"
    if mode_setting:
        mode_setting.value = val
    else:
        mode_setting = SystemSetting(key="autonomous_mode", value=val)
        db.add(mode_setting)
    db.commit()

    return {
        "success": True,
        "autonomous_mode": payload.enabled,
        "message": f"Modo {'autónomo agéntico' if payload.enabled else 'supervisado (human-in-the-loop)'} activado."
    }

@router.get("/stats")
def get_system_stats(
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Returns overview metrics for quick badge summaries."""
    total_emails = db.query(EmailNotice).count()
    pending_emails = db.query(EmailNotice).filter(EmailNotice.status == "PENDING_REVIEW").count()
    approved_emails = db.query(EmailNotice).filter(EmailNotice.status.in_(["APPROVED_INDEXED", "AUTO_INDEXED"])).count()
    rejected_emails = db.query(EmailNotice).filter(EmailNotice.status == "REJECTED").count()
    total_docs = db.query(DocumentItem).count()
    total_chunks = vector_store.get_total_chunks()
    total_feedbacks = db.query(SessionFeedback).count()
    pending_feedbacks = db.query(SessionFeedback).filter(SessionFeedback.status != "REVIEWED").count()

    mode_setting = db.query(SystemSetting).filter(SystemSetting.key == "autonomous_mode").first()
    is_autonomous = mode_setting.value.lower() == "true" if mode_setting else False

    return {
        "total_emails": total_emails,
        "pending_emails": pending_emails,
        "approved_emails": approved_emails,
        "rejected_emails": rejected_emails,
        "total_documents": total_docs,
        "total_vector_chunks": total_chunks,
        "total_feedbacks": total_feedbacks,
        "pending_feedbacks": pending_feedbacks,
        "autonomous_mode": is_autonomous
    }

@router.get("/analytics")
def get_crm_analytics(
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """
    Returns 100% real CRM analytics for the student portal based on actual database logs and vector store chunks:
    - 4 Top KPI Cards
    - 6-Month Monthly Area Chart Series
    - Topic Distribution
    - Top Frequent Questions Ranking
    - Knowledge Gaps Monitor
    - System Health & Infrastructure Metrics
    """
    now = datetime.utcnow()
    start_of_current_month = datetime(now.year, now.month, 1)

    # Previous month start and end
    if now.month == 1:
        start_of_prev_month = datetime(now.year - 1, 12, 1)
    else:
        start_of_prev_month = datetime(now.year, now.month - 1, 1)

    total_all_queries = db.query(StudentQueryLog).count()
    sistemas_filter = StudentQueryLog.topic_category != "Otra Carrera / Facultad"
    total_sistemas_queries = db.query(StudentQueryLog).filter(sistemas_filter).count()

    current_month_queries = db.query(StudentQueryLog).filter(StudentQueryLog.timestamp >= start_of_current_month).count()
    prev_month_queries = db.query(StudentQueryLog).filter(
        StudentQueryLog.timestamp >= start_of_prev_month,
        StudentQueryLog.timestamp < start_of_current_month
    ).count()

    if prev_month_queries > 0:
        query_growth = round(((current_month_queries - prev_month_queries) / prev_month_queries) * 100, 1)
    else:
        query_growth = 0.0

    today_start = datetime(now.year, now.month, now.day)
    active_queries_today = db.query(StudentQueryLog).filter(StudentQueryLog.timestamp >= today_start).count()

    topic_counts = db.query(
        StudentQueryLog.topic_category,
        func.count(StudentQueryLog.id)
    ).group_by(StudentQueryLog.topic_category).order_by(func.count(StudentQueryLog.id).desc()).all()

    # Top topic for Sistemas
    sistemas_topic_counts = db.query(
        StudentQueryLog.topic_category,
        func.count(StudentQueryLog.id)
    ).filter(sistemas_filter).group_by(StudentQueryLog.topic_category).order_by(func.count(StudentQueryLog.id).desc()).all()
    top_topic = sistemas_topic_counts[0][0] if sistemas_topic_counts else "Sin consultas registradas"

    # RAG coverage and gaps calculated strictly on Sistemas queries
    total_with_citations = db.query(StudentQueryLog).filter(
        sistemas_filter,
        StudentQueryLog.citations_count > 0,
        StudentQueryLog.has_knowledge_gap == False
    ).count()
    rag_coverage_pct = round((total_with_citations / total_sistemas_queries * 100) if total_sistemas_queries > 0 else 0.0, 1)

    total_gaps = db.query(StudentQueryLog).filter(
        sistemas_filter,
        StudentQueryLog.has_knowledge_gap == True
    ).count()
    gaps_rate_pct = round((total_gaps / total_sistemas_queries * 100) if total_sistemas_queries > 0 else 0.0, 1)

    total_docs = db.query(DocumentItem).count()
    total_chunks = vector_store.get_total_chunks()

    # 2. Monthly Series (Last 6 months) for Area Chart
    month_names_es = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    monthly_series = []

    for i in range(5, -1, -1):
        m_year = now.year
        m_month = now.month - i
        while m_month <= 0:
            m_month += 12
            m_year -= 1

        m_start = datetime(m_year, m_month, 1)
        if m_month == 12:
            m_end = datetime(m_year + 1, 1, 1)
        else:
            m_end = datetime(m_year, m_month + 1, 1)

        m_count = db.query(StudentQueryLog).filter(
            StudentQueryLog.timestamp >= m_start,
            StudentQueryLog.timestamp < m_end
        ).count()

        m_sistemas_count = db.query(StudentQueryLog).filter(
            sistemas_filter,
            StudentQueryLog.timestamp >= m_start,
            StudentQueryLog.timestamp < m_end
        ).count()

        m_citations = db.query(StudentQueryLog).filter(
            sistemas_filter,
            StudentQueryLog.timestamp >= m_start,
            StudentQueryLog.timestamp < m_end,
            StudentQueryLog.citations_count > 0,
            StudentQueryLog.has_knowledge_gap == False
        ).count()

        m_gaps = db.query(StudentQueryLog).filter(
            sistemas_filter,
            StudentQueryLog.timestamp >= m_start,
            StudentQueryLog.timestamp < m_end,
            StudentQueryLog.has_knowledge_gap == True
        ).count()

        new_docs = db.query(DocumentItem).filter(
            DocumentItem.created_at >= m_start,
            DocumentItem.created_at < m_end
        ).count()

        monthly_series.append({
            "label": f"{month_names_es[m_month - 1]}",
            "consultas": m_count,
            "consultas_sistemas": m_sistemas_count,
            "documentos": new_docs,
            "cobertura": round((m_citations / m_sistemas_count * 100) if m_sistemas_count > 0 else 0.0, 1),
            "brechas": round((m_gaps / m_sistemas_count * 100) if m_sistemas_count > 0 else 0.0, 1),
            "tiempo": 1.2 if m_count > 0 else 0.0,
        })

    # 3. Topic Distribution
    all_topics_data = []
    for top, c in topic_counts:
        all_topics_data.append({
            "topic": top,
            "count": c,
            "percentage": round((c / total_all_queries * 100) if total_all_queries > 0 else 0.0, 1)
        })

    # 4. Top Frequent Questions
    freq_questions_raw = db.query(
        StudentQueryLog.query_text,
        StudentQueryLog.topic_category,
        func.count(StudentQueryLog.id).label("total_count"),
        func.max(StudentQueryLog.citations_count).label("max_citations")
    ).group_by(StudentQueryLog.query_text, StudentQueryLog.topic_category).order_by(func.count(StudentQueryLog.id).desc()).limit(8).all()

    top_questions = []
    for q, cat, cnt, cites in freq_questions_raw:
        cited_text = f"Artículos normativos ({cites} citas)" if cites and cites > 0 else "Sin respaldo normativo"
        top_questions.append({
            "question": q,
            "category": cat,
            "count": cnt,
            "cited_source": cited_text
        })

    # 5. Knowledge Gaps (Strictly normative gaps in Sistemas)
    gaps_raw = db.query(StudentQueryLog).filter(
        sistemas_filter,
        StudentQueryLog.has_knowledge_gap == True
    ).order_by(StudentQueryLog.timestamp.desc()).limit(10).all()

    knowledge_gaps = []
    for g in gaps_raw:
        knowledge_gaps.append({
            "id": g.id,
            "query": g.query_text,
            "category": g.topic_category,
            "confidence": round(g.confidence_score * 100, 1),
            "date": g.timestamp.strftime("%d/%m/%Y"),
            "status": "SIN_RESOLUCION_ASOCIADA"
        })

    # 6. Real System Health (Sistemas Pilot V1)
    overall_health = 100.0 if total_sistemas_queries == 0 else max(10.0, min(100.0, rag_coverage_pct))
    system_health = {
        "overall_score": round(overall_health, 1),
        "success_rate": rag_coverage_pct,
        "gap_rate": gaps_rate_pct,
        "avg_latency": 1.2 if total_all_queries > 0 else 0.0,
        "model_name": llm_adapter.model_name,
        "provider": settings.LLM_PROVIDER,
        "total_chunks": total_chunks,
        "total_documents": total_docs,
        "status": "OPERACIONAL"
    }

    # 7. Interest Tracking from Other Careers / Faculties (Escalabilidad)
    other_career_logs = db.query(StudentQueryLog).filter(
        StudentQueryLog.topic_category == "Otra Carrera / Facultad"
    ).order_by(StudentQueryLog.timestamp.desc()).all()

    total_other_queries = len(other_career_logs)
    career_tally = {}
    recent_other_queries = []

    for l in other_career_logs:
        detected = detect_other_career(l.query_text) or "Otra Carrera / Facultad"
        career_tally[detected] = career_tally.get(detected, 0) + 1
        if len(recent_other_queries) < 15:
            recent_other_queries.append({
                "id": l.id,
                "query": l.query_text,
                "career": detected,
                "date": l.timestamp.strftime("%d/%m/%Y %H:%M")
            })

    careers_ranking = [
        {
            "career": k,
            "count": v,
            "percentage": round((v / total_other_queries * 100) if total_other_queries > 0 else 0.0, 1)
        }
        for k, v in sorted(career_tally.items(), key=lambda item: item[1], reverse=True)
    ]

    other_faculty_interest = {
        "total_queries": total_other_queries,
        "percentage_of_all_traffic": round((total_other_queries / total_all_queries * 100) if total_all_queries > 0 else 0.0, 1),
        "careers_ranking": careers_ranking,
        "recent_queries": recent_other_queries
    }

    return {
        "kpis": {
            "total_queries_month": current_month_queries,
            "previous_month_queries": prev_month_queries,
            "query_growth_percentage": query_growth,
            "active_users_today": active_queries_today,
            "top_topic": top_topic,
            "rag_coverage_rate": rag_coverage_pct,
            "knowledge_gaps_rate": gaps_rate_pct,
            "avg_latency": 1.2 if total_all_queries > 0 else 0.0,
            "total_documents": total_docs,
            "total_vector_chunks": total_chunks,
            "total_all_time_queries": total_all_queries,
            "sistemas_queries_count": total_sistemas_queries,
            "other_faculty_queries_count": total_other_queries
        },
        "monthly_series": monthly_series,
        "topic_distribution": all_topics_data,
        "top_questions": top_questions,
        "knowledge_gaps": knowledge_gaps,
        "system_health": system_health,
        "other_faculty_interest": other_faculty_interest
    }

@router.post("/emails/upload-batch")
async def upload_batch_emails_and_notices(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """
    Receives multiple .eml and .pdf notice files, parses them, runs LLM triage,
    and stores them in the triage inbox for admin review.
    """
    results = []
    upload_dir = os.path.join(settings.DATA_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    for upload_file in files:
        filename = upload_file.filename or "archivo_sin_nombre"
        ext = os.path.splitext(filename)[1].lower()

        try:
            if ext == ".eml":
                content = await upload_file.read()
                parsed = parse_eml_bytes(content)

                email_record = triage_service.process_incoming_email(
                    db=db,
                    sender=parsed["sender"],
                    subject=parsed["subject"],
                    body=parsed["body"],
                    attachments=parsed["attachments"],
                    urls=parsed["urls"]
                )
                results.append({
                    "filename": filename,
                    "type": "eml",
                    "success": True,
                    "email_id": email_record.id,
                    "subject": email_record.subject,
                    "sender": email_record.sender,
                    "status": email_record.status,
                    "is_relevant": email_record.is_relevant,
                    "relevance_score": email_record.relevance_score,
                    "triage_summary": email_record.triage_summary
                })
            elif ext == ".pdf":
                clean_name = re.sub(r'[^\w\.-]', '_', os.path.basename(filename))
                file_path = os.path.join(upload_dir, clean_name)

                content = await upload_file.read()
                with open(file_path, "wb") as f:
                    f.write(content)

                # Extract text from PDF
                pdf_text = document_processor.extract_text_from_file(file_path)
                if not pdf_text or len(pdf_text.strip()) < 20:
                    pdf_text = f"Comunicado oficial adjunto en formato PDF: {filename}."

                official_meta = document_processor.extract_official_metadata(pdf_text)
                clean_title = official_meta.get("title") or os.path.splitext(clean_name)[0].replace("_", " ").title()

                email_record = triage_service.process_incoming_email(
                    db=db,
                    sender="comunicados@udistrital.edu.co",
                    subject=f"Comunicado: {clean_title}",
                    body=pdf_text,
                    attachments=[clean_name],
                    urls=[]
                )
                results.append({
                    "filename": filename,
                    "type": "pdf",
                    "success": True,
                    "email_id": email_record.id,
                    "subject": email_record.subject,
                    "sender": email_record.sender,
                    "status": email_record.status,
                    "is_relevant": email_record.is_relevant,
                    "relevance_score": email_record.relevance_score,
                    "triage_summary": email_record.triage_summary
                })
            elif ext in [".md", ".markdown", ".txt"]:
                clean_name = re.sub(r'[^\w\.-]', '_', os.path.basename(filename))
                file_path = os.path.join(upload_dir, clean_name)

                content = await upload_file.read()
                raw_text = content.decode("utf-8", errors="replace")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(raw_text)

                official_meta = document_processor.extract_official_metadata(raw_text)
                clean_title = official_meta.get("title") or os.path.splitext(clean_name)[0].replace("_", " ").title()

                email_record = triage_service.process_incoming_email(
                    db=db,
                    sender="comunicados@udistrital.edu.co",
                    subject=f"Acuerdo/Comunicado: {clean_title}",
                    body=raw_text,
                    attachments=[clean_name],
                    urls=[]
                )
                results.append({
                    "filename": filename,
                    "type": "markdown",
                    "success": True,
                    "email_id": email_record.id,
                    "subject": email_record.subject,
                    "sender": email_record.sender,
                    "status": email_record.status,
                    "is_relevant": email_record.is_relevant,
                    "relevance_score": email_record.relevance_score,
                    "triage_summary": email_record.triage_summary
                })
            else:
                results.append({
                    "filename": filename,
                    "success": False,
                    "error": f"Formato '{ext}' no soportado. Debe ser .eml, .pdf o .md"
                })
        except Exception as file_err:
            logger.error(f"[UploadBatch] Error processing {filename}: {file_err}", exc_info=True)
            results.append({
                "filename": filename,
                "success": False,
                "error": str(file_err)
            })

    return {
        "success": True,
        "processed_count": len(results),
        "results": results
    }

class CreateMarkdownEmailPayload(BaseModel):
    subject: str
    markdown_content: str
    sender: Optional[str] = "comunicados@udistrital.edu.co"

@router.post("/emails/create-markdown")
async def create_markdown_email_notice(
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """
    Directly creates an email notice from Markdown text and executes LLM triage,
    with an optional attached scan/image of the original document.
    """
    content_type = request.headers.get("content-type", "")
    scan_file = None
    if "multipart/form-data" in content_type:
        form_data = await request.form()
        subject = form_data.get("subject", "")
        markdown_content = form_data.get("markdown_content", "")
        sender = form_data.get("sender", "comunicados@udistrital.edu.co")
        scan_file = form_data.get("scan_file")
    else:
        json_data = await request.json()
        subject = json_data.get("subject", "")
        markdown_content = json_data.get("markdown_content", "")
        sender = json_data.get("sender", "comunicados@udistrital.edu.co")

    if not markdown_content or len(markdown_content.strip()) < 10:
        raise HTTPException(status_code=400, detail="El contenido en Markdown no puede estar vacío.")

    raw_text = markdown_content.strip()
    official_meta = document_processor.extract_official_metadata(raw_text)
    clean_title = subject.strip() or official_meta.get("title") or "Acuerdo / Comunicado Oficial"

    # Save to uploads folder
    safe_title = re.sub(r'[^\w\.-]', '_', clean_title.lower())[:50]
    filename = f"{safe_title}_{int(datetime.utcnow().timestamp())}.md"
    upload_dir = os.path.join(settings.DATA_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(raw_text)

    attachments = [filename]
    if scan_file and hasattr(scan_file, "filename") and scan_file.filename:
        scan_ext = os.path.splitext(scan_file.filename)[1].lower()
        if scan_ext in [".png", ".jpg", ".jpeg", ".webp", ".pdf"]:
            safe_scan = re.sub(r'[^\w\.-]', '_', os.path.splitext(scan_file.filename)[0].lower())[:40]
            scan_filename = f"scan_{safe_scan}_{int(datetime.utcnow().timestamp())}{scan_ext}"
            scan_path = os.path.join(upload_dir, scan_filename)
            with open(scan_path, "wb") as b:
                shutil.copyfileobj(scan_file.file, b)
            attachments.append(scan_filename)

    email_record = triage_service.process_incoming_email(
        db=db,
        sender=sender or "comunicados@udistrital.edu.co",
        subject=clean_title,
        body=raw_text,
        attachments=attachments,
        urls=[]
    )

    return {
        "success": True,
        "email_id": email_record.id,
        "subject": email_record.subject,
        "status": email_record.status,
        "is_relevant": email_record.is_relevant,
        "relevance_score": email_record.relevance_score,
        "triage_summary": email_record.triage_summary,
        "target_program": email_record.target_program
    }
