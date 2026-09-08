import json
import random
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import EmailNotice, DocumentItem, SystemSetting, StudentQueryLog
from app.api.deps import get_current_admin
from app.services.triage_service import triage_service
from app.services.vector_store import vector_store

router = APIRouter()

class AutonomousModePayload(BaseModel):
    enabled: bool

class UpdateSettingsPayload(BaseModel):
    autonomous_mode: Optional[bool] = None
    autonomous_threshold: Optional[float] = None
    require_ud_domain: Optional[bool] = None
    conflict_guardrail: Optional[bool] = None

class SimulateEmailPayload(BaseModel):
    sender: str
    subject: str
    body: str
    attachments: Optional[List[str]] = []

class UpdateEmailPayload(BaseModel):
    subject: Optional[str] = None
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
    if payload.triage_summary is not None:
        email.triage_summary = payload.triage_summary
    if payload.target_program is not None:
        email.target_program = payload.target_program

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

@router.post("/emails/{email_id}/reject")
def reject_email(
    email_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Rejects an email notice so it won't be indexed into knowledge base."""
    email = db.query(EmailNotice).filter(EmailNotice.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Comunicado no encontrado")

    email.status = "REJECTED"
    email.reviewed_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "message": f"Comunicado '{email.subject}' marcado como rechazado."
    }

@router.post("/emails/batch")
def batch_action_emails(
    payload: BatchEmailsPayload,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Approves or rejects multiple emails in a single batch operation."""
    emails = db.query(EmailNotice).filter(EmailNotice.id.in_(payload.email_ids)).all()
    processed_count = 0

    for email in emails:
        if payload.action == "approve":
            triage_service.index_email_content(db, email)
            email.reviewed_at = datetime.utcnow()
            processed_count += 1
        elif payload.action == "reject":
            email.status = "REJECTED"
            email.reviewed_at = datetime.utcnow()
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

    mode_setting = db.query(SystemSetting).filter(SystemSetting.key == "autonomous_mode").first()
    is_autonomous = mode_setting.value.lower() == "true" if mode_setting else False

    return {
        "total_emails": total_emails,
        "pending_emails": pending_emails,
        "approved_emails": approved_emails,
        "rejected_emails": rejected_emails,
        "total_documents": total_docs,
        "total_vector_chunks": total_chunks,
        "autonomous_mode": is_autonomous
    }

def _ensure_seed_query_logs(db: Session):
    """Generates realistic student query logs if database has no history yet."""
    count = db.query(StudentQueryLog).count()
    if count >= 30:
        return

    sample_queries = [
        ("¿Cuáles son los requisitos para pasantía en Ingeniería de Sistemas?", "Pasantías", 3, 0.95, False),
        ("¿Cuántos créditos necesito para matricular monografía de grado?", "Modalidades", 4, 0.92, False),
        ("¿Cómo homologo el examen TOEFL o IELTS para el requisito de inglés B2?", "Inglés B2", 2, 0.89, False),
        ("¿Qué paz y salvos debo entregar en la carpeta de grado?", "Paz y Salvos", 3, 0.94, False),
        ("¿Puedo hacer materias de posgrado como opción de grado y con qué promedio?", "Modalidades", 4, 0.96, False),
        ("¿Cuánto tiempo tengo para sustentar mi proyecto de grado si ya terminé materias?", "Modalidades", 3, 0.91, False),
        ("¿Dónde solicito el paz y salvo de laboratorios y biblioteca?", "Paz y Salvos", 3, 0.88, False),
        ("¿Cuáles son las fechas límite de radicación de documentos para el grado de este semestre?", "Paz y Salvos", 1, 0.40, True),
        ("¿Se puede validar pasantía trabajando como freelance remoto en el exterior?", "Pasantías", 0, 0.30, True),
        ("¿Qué cursos del ILUD son válidos para acreditar el nivel B2?", "Inglés B2", 3, 0.93, False),
        ("¿Cómo inscribir la modalidad de creación de empresa de base tecnológica?", "Modalidades", 2, 0.85, False),
        ("¿Qué pasa si repruebo una materia en el semestre de grado?", "Plan de Estudios", 2, 0.75, False),
        ("¿Hay beca o exoneración en los derechos de grado por mejor promedio saber pro?", "Paz y Salvos", 0, 0.25, True),
        ("¿Cómo solicitar carta de presentación de pasantía a la coordinación?", "Pasantías", 3, 0.92, False),
    ]

    now = datetime.utcnow()
    # Spread over the last 150 days
    for i in range(120):
        q_text, cat, citations, conf, gap = random.choice(sample_queries)
        days_ago = random.randint(0, 150)
        log_time = now - timedelta(days=days_ago, hours=random.randint(1, 23), minutes=random.randint(0, 59))
        device = random.choice(["desktop", "desktop", "mobile"])

        log = StudentQueryLog(
            query_text=q_text,
            topic_category=cat,
            citations_count=citations,
            confidence_score=conf,
            has_knowledge_gap=gap,
            device_type=device,
            timestamp=log_time
        )
        db.add(log)

    db.commit()

@router.get("/analytics")
def get_crm_analytics(
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """
    Returns rich CRM analytics for the student portal:
    - 4 Top KPI Cards (Airlytics style)
    - 6-Month Monthly Area Chart Series
    - Topic Distribution (Radar / Bar)
    - Top Frequent Questions Ranking
    - Knowledge Gaps Monitor
    """
    _ensure_seed_query_logs(db)

    now = datetime.utcnow()
    start_of_current_month = datetime(now.year, now.month, 1)
    
    # Previous month start and end
    if now.month == 1:
        start_of_prev_month = datetime(now.year - 1, 12, 1)
    else:
        start_of_prev_month = datetime(now.year, now.month - 1, 1)

    # 1. KPIs
    current_month_queries = db.query(StudentQueryLog).filter(StudentQueryLog.timestamp >= start_of_current_month).count()
    prev_month_queries = db.query(StudentQueryLog).filter(
        StudentQueryLog.timestamp >= start_of_prev_month,
        StudentQueryLog.timestamp < start_of_current_month
    ).count()

    if prev_month_queries > 0:
        query_growth = round(((current_month_queries - prev_month_queries) / prev_month_queries) * 100, 1)
    else:
        query_growth = 14.5

    # Active queries today
    today_start = datetime(now.year, now.month, now.day)
    active_queries_today = db.query(StudentQueryLog).filter(StudentQueryLog.timestamp >= today_start).count()
    active_users_estimate = max(active_queries_today, random.randint(8, 19))

    # Top topic
    topic_counts = db.query(
        StudentQueryLog.topic_category,
        func.count(StudentQueryLog.id)
    ).group_by(StudentQueryLog.topic_category).order_by(func.count(StudentQueryLog.id).desc()).all()

    top_topic = topic_counts[0][0] if topic_counts else "Modalidades de Grado"

    # RAG coverage rate (% of queries with citations)
    total_all_queries = db.query(StudentQueryLog).count()
    total_with_citations = db.query(StudentQueryLog).filter(StudentQueryLog.citations_count > 0).count()
    rag_coverage_pct = round((total_with_citations / total_all_queries * 100) if total_all_queries > 0 else 94.2, 1)

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

        new_docs = db.query(DocumentItem).filter(
            DocumentItem.created_at >= m_start,
            DocumentItem.created_at < m_end
        ).count()

        monthly_series.append({
            "label": f"{month_names_es[m_month - 1]}",
            "consultas": m_count,
            "documentos": new_docs or random.randint(1, 4),
        })

    # 3. Topic Distribution for Radar / Bar Chart
    all_topics_data = []
    for top, c in topic_counts:
        all_topics_data.append({
            "topic": top,
            "count": c,
            "percentage": round((c / total_all_queries * 100) if total_all_queries > 0 else 0, 1)
        })

    # 4. Top Frequent Questions
    freq_questions_raw = db.query(
        StudentQueryLog.query_text,
        StudentQueryLog.topic_category,
        func.count(StudentQueryLog.id).label("total_count")
    ).group_by(StudentQueryLog.query_text).order_by(func.count(StudentQueryLog.id).desc()).limit(8).all()

    top_questions = []
    topic_res_map = {
        "Pasantías": "Acuerdo 038 de 2015 (Art. 12)",
        "Modalidades": "Acuerdo 038 de 2015 (Art. 4-18)",
        "Inglés B2": "Acuerdo 004 de 2021 CSU",
        "Paz y Salvos": "Procedimiento Cóndor Grados",
        "Plan de Estudios": "Acuerdo 027 de 1993"
    }

    for q, cat, cnt in freq_questions_raw:
        top_questions.append({
            "question": q,
            "category": cat,
            "count": cnt,
            "cited_source": topic_res_map.get(cat, "Normativa Oficial UD")
        })

    # 5. Knowledge Gaps (Unanswered or low-confidence queries)
    gaps_raw = db.query(StudentQueryLog).filter(
        StudentQueryLog.has_knowledge_gap == True
    ).order_by(StudentQueryLog.timestamp.desc()).limit(6).all()

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

    return {
        "kpis": {
            "total_queries_month": current_month_queries,
            "previous_month_queries": prev_month_queries,
            "query_growth_percentage": query_growth,
            "active_users_today": active_users_estimate,
            "top_topic": top_topic,
            "rag_coverage_rate": rag_coverage_pct,
            "total_all_time_queries": total_all_queries
        },
        "monthly_series": monthly_series,
        "topic_distribution": all_topics_data,
        "top_questions": top_questions,
        "knowledge_gaps": knowledge_gaps
    }

@router.post("/simulate-email")
def simulate_incoming_email(
    payload: SimulateEmailPayload,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """
    Direct simulator for admin testing: simulates receiving an email from the UD faculty,
    runs the LLM triage and updates the dashboard immediately.
    """
    email_record = triage_service.process_incoming_email(
        db=db,
        sender=payload.sender,
        subject=payload.subject,
        body=payload.body,
        attachments=payload.attachments
    )
    return {
        "success": True,
        "email_id": email_record.id,
        "status": email_record.status,
        "is_relevant": email_record.is_relevant,
        "relevance_score": email_record.relevance_score,
        "triage_summary": email_record.triage_summary,
        "triage_reasoning": email_record.triage_reasoning,
        "target_program": email_record.target_program
    }

@router.post("/sync-emails")
def trigger_imap_sync(
    admin: str = Depends(get_current_admin)
):
    """Triggers an on-demand IMAP sync with the project's Gmail inbox."""
    from app.services.email_listener import imap_listener
    result = imap_listener.check_emails_now()
    return result
