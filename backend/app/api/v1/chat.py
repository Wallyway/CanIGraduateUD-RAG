import json
import urllib.parse
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.services.rag_service import rag_service, is_other_career_or_faculty
from app.db.session import SessionLocal, get_db
from app.db.models import StudentQueryLog, SessionFeedback
from app.api.deps import get_current_admin

router = APIRouter()

class ChatTurn(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    query: str
    history: Optional[List[ChatTurn]] = []

def classify_topic(query: str) -> str:
    if is_other_career_or_faculty(query):
        return "Otra Carrera / Facultad"
    q = query.lower()
    if any(w in q for w in ["pasant", "practic", "empresa", "carta de presentaci"]):
        return "Pasantías"
    elif any(w in q for w in ["modalidad", "monograf", "grado", "tesis", "posgrado", "semillero"]):
        return "Modalidades"
    elif any(w in q for w in ["ingl", "b2", "ilud", "idioma", "acreditaci"]):
        return "Inglés B2"
    elif any(w in q for w in ["paz y salvo", "carpeta", "secretar", "ventanilla", "pago", "derechos"]):
        return "Paz y Salvos"
    elif any(w in q for w in ["crédito", "credito", "matricul", "cancelar", "adicionar", "promedio"]):
        return "Plan de Estudios"
    return "Normativa General"

@router.post("/stream")
def stream_chat_response(payload: ChatRequest):
    """
    Public student chat endpoint that streams answers with official citations
    using Server-Sent Events (SSE).
    """
    history_dicts = [{"role": h.role, "content": h.content} for h in payload.history] if payload.history else []

    def event_generator():
        citation_count = 0
        collected_tokens = []
        try:
            for event in rag_service.answer_stream(payload.query, history_dicts):
                if event.get("type") == "token":
                    collected_tokens.append(event.get("content", ""))
                elif event.get("type") == "citations":
                    citation_count = len(event.get("citations", []))
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as stream_err:
            print(f"[ChatStream] Streaming exception: {stream_err}")
            err_msg = f"\n\n*(Error temporal en la transmisión: {str(stream_err)})*"
            yield f"data: {json.dumps({'type': 'token', 'content': err_msg})}\n\n"
        finally:
            try:
                full_text = "".join(collected_tokens).lower()
                gap_phrases = [
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
                    "no están documentados",
                    "no están documentadas",
                    "consultar directamente ante la coordinación",
                    "consultar directamente con la coordinación",
                    "consultar directamente ante la secretaría",
                    "consultar directamente con la secretaría",
                    "consultar ante la coordinación del proyecto curricular",
                    "consultar con la coordinación del proyecto curricular",
                    "trámite específico"
                ]
                is_other = is_other_career_or_faculty(payload.query)
                if is_other:
                    has_gap = False
                    confidence = 1.0
                else:
                    has_gap = (citation_count == 0) or any(phrase in full_text for phrase in gap_phrases)
                    confidence = 0.25 if (citation_count == 0) else (0.45 if has_gap else (1.0 if citation_count >= 2 else 0.85))

                db = SessionLocal()
                log = StudentQueryLog(
                    query_text=payload.query,
                    topic_category=classify_topic(payload.query),
                    citations_count=citation_count,
                    confidence_score=confidence,
                    has_knowledge_gap=has_gap,
                    device_type="desktop"
                )
                db.add(log)
                db.commit()
                db.close()
            except Exception as log_err:
                print(f"[ChatLog] Error logging query: {log_err}")

            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

class SessionFeedbackPayload(BaseModel):
    session_id: Optional[str] = None
    user_email: Optional[str] = None
    feedback_type: Optional[str] = "general"
    rating: Optional[int] = None
    comments: str
    include_transcript: bool = True
    messages: Optional[List[Dict[str, Any]]] = None

from app.services.email_dispatcher import email_dispatcher

@router.post("/feedback")
def submit_session_feedback(payload: SessionFeedbackPayload, db: Session = Depends(get_db)):
    """
    Receives student feedback for a specific chat session, optionally including
    the transcript of the conversation, destined for canigraduateud@gmail.com.
    """
    if not payload.comments or not payload.comments.strip():
        raise HTTPException(status_code=400, detail="El comentario no puede estar vacío.")

    transcript_str = None
    if payload.include_transcript and payload.messages:
        try:
            transcript_str = json.dumps(payload.messages, ensure_ascii=False)
        except Exception:
            transcript_str = str(payload.messages)

    feedback_record = SessionFeedback(
        session_id=payload.session_id,
        user_email=payload.user_email.strip() if payload.user_email else None,
        feedback_type=payload.feedback_type or "general",
        rating=payload.rating,
        comments=payload.comments.strip(),
        has_transcript=payload.include_transcript and bool(payload.messages),
        transcript_json=transcript_str,
        target_email="canigraduateud@gmail.com",
        status="RECEIVED"
    )
    db.add(feedback_record)
    db.commit()
    db.refresh(feedback_record)

    # Dispatch email via SMTP or prepare direct web compose links
    disp_result = email_dispatcher.send_feedback_email(
        feedback_id=feedback_record.id,
        session_id=payload.session_id,
        feedback_type=payload.feedback_type or "general",
        comments=payload.comments.strip(),
        rating=payload.rating,
        user_email=payload.user_email.strip() if payload.user_email else None,
        messages=payload.messages if payload.include_transcript else None,
        target_email="canigraduateud@gmail.com"
    )

    if disp_result.get("sent"):
        feedback_record.status = "SENT_VIA_SMTP"
        db.commit()

    return {
        "success": True,
        "feedback_id": feedback_record.id,
        "target_email": "canigraduateud@gmail.com",
        "email_sent": disp_result.get("sent", False),
        "has_smtp_configured": disp_result.get("has_smtp_configured", False),
        "message": (
            "Feedback enviado exitosamente a canigraduateud@gmail.com"
            if disp_result.get("sent")
            else "Feedback registrado exitosamente en el sistema"
        ),
        "mailto_url": disp_result.get("mailto_url"),
        "gmail_compose_url": disp_result.get("gmail_compose_url")
    }

@router.get("/feedbacks")
def list_session_feedbacks(
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Lists recent session feedbacks for administrative review."""
    feedbacks = db.query(SessionFeedback).order_by(SessionFeedback.created_at.desc()).limit(limit).all()
    results = []
    for f in feedbacks:
        results.append({
            "id": f.id,
            "session_id": f.session_id,
            "user_email": f.user_email,
            "feedback_type": f.feedback_type,
            "rating": f.rating,
            "comments": f.comments,
            "has_transcript": f.has_transcript,
            "transcript_json": f.transcript_json,
            "target_email": f.target_email,
            "status": f.status,
            "created_at": f.created_at.isoformat() if f.created_at else None
        })
    return results

class UpdateFeedbackStatusPayload(BaseModel):
    status: str

@router.patch("/feedbacks/{feedback_id}/status")
def update_feedback_status(
    feedback_id: int,
    payload: UpdateFeedbackStatusPayload,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Updates the processing status of a feedback (e.g. REVIEWED, RECEIVED)."""
    f = db.query(SessionFeedback).filter(SessionFeedback.id == feedback_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Feedback no encontrado")
    f.status = payload.status
    db.commit()
    return {"success": True, "id": f.id, "status": f.status}

@router.delete("/feedbacks/{feedback_id}")
def delete_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Deletes a feedback record from the database."""
    f = db.query(SessionFeedback).filter(SessionFeedback.id == feedback_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Feedback no encontrado")
    db.delete(f)
    db.commit()
    return {"success": True, "message": "Feedback eliminado exitosamente"}


