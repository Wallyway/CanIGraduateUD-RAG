import json
import urllib.parse
import threading
import queue
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.services.rag_service import rag_service, is_other_career_or_faculty
from app.db.session import SessionLocal, get_db
from app.db.models import StudentQueryLog, SessionFeedback
from app.api.deps import get_current_admin
from app.core.config import settings
from app.core import security_guardrails
from app.core.security_guardrails import (
    extract_client_info,
    inspect_query_safety,
    strike_manager,
    rate_limiter,
    STREAM_CONCURRENCY_SEMAPHORE
)
from app.core.redis_cache import redis_cache
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)


class SemaphoreReleaseGuard:
    """
    Ensures that an acquired semaphore permit is released unconditionally
    exactly once upon stream completion, exception, client disconnect (GeneratorExit),
    or garbage collection.
    """
    def __init__(self, semaphore: threading.Semaphore):
        self.semaphore = semaphore
        self.released = False
        self._lock = threading.Lock()

    def release(self):
        with self._lock:
            if not self.released:
                self.released = True
                try:
                    self.semaphore.release()
                except Exception as exc:
                    logger.warning(f"[ConcurrencyGuard] Error releasing stream semaphore: {exc}")

    def __del__(self):
        self.release()

# Bounded executor for asynchronous background cache writes
_CACHE_WRITE_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cache_writer")

def _submit_cache_write(query: str, answer: str, citations: list, topic: str):
    """Safely queues background cache write without thread exhaustion."""
    try:
        _CACHE_WRITE_EXECUTOR.submit(redis_cache.set, query, answer, citations, topic)
    except Exception as exc:
        logger.warning(f"[ChatCache] Failed to submit async cache write: {exc}")

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
def stream_chat_response(
    request: Request,
    payload: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Public student chat endpoint that streams answers with official citations
    using Server-Sent Events (SSE), protected by multi-factor rate limiting,
    anti-prompting defense, and a strict 3-strike 24h penalty system.
    """
    # 1. Identify Client (IP, Subnet, Device ID, MAC, User-Agent)
    client_info = extract_client_info(request)
    client_ip = client_info["ip"]
    subnet = client_info["subnet"]
    device_id = client_info["device_id"]
    client_mac = client_info["mac"]
    user_agent = client_info["user_agent"]
    client_key = f"{client_ip}_{client_mac}_{device_id}" if (device_id or client_mac) else client_ip

    # 2. Gate 1: Check Active 24-Hour Ban
    is_banned, remaining_seconds, ban_reason = strike_manager.check_penalty(
        client_ip, subnet, device_id, client_mac
    )
    if is_banned:
        hours = remaining_seconds // 3600
        mins = (remaining_seconds % 3600) // 60
        ban_msg = (
            f"🚫 **Acceso Suspendido por 24 Horas (3/3 Strikes de Abuso):**\n\n"
            f"Tu dispositivo e IP (`{client_ip}`) se encuentran bajo una suspensión temporal de 24 horas "
            f"por consultas no autorizadas o uso indebido reiterado (Motivo: *{ban_reason}*).\n\n"
            f"⏳ **Tiempo restante de penalización:** {hours} horas y {mins} minutos.\n\n"
            f"🔒 *Esta restricción previene el consumo desmedido de tokens de la Universidad Distrital.*"
        )
        def banned_stream():
            yield f"data: {json.dumps({'type': 'token', 'content': ban_msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'citations', 'citations': []}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            banned_stream(),
            media_type="text/event-stream",
            status_code=status.HTTP_403_FORBIDDEN,
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "X-Security-Banned": "true",
                "Retry-After": str(remaining_seconds)
            }
        )

    # 3. Gate 2: Volumetric Rate Limiting (max 10 req/min per client)
    is_rate_limited, retry_after = rate_limiter.is_rate_limited(
        endpoint_key="chat_stream",
        client_key=client_key,
        max_requests=10,
        window_seconds=60
    )
    if is_rate_limited:
        limit_msg = (
            f"⏳ **Límite de Consultas Excedido (Rate Limit):**\n\n"
            f"Has enviado demasiadas preguntas en un lapso corto de tiempo. "
            f"Por favor espera **{retry_after} segundos** antes de enviar una nueva consulta "
            f"para garantizar un acceso fluido y equitativo para todos los estudiantes."
        )
        def rate_limit_stream():
            yield f"data: {json.dumps({'type': 'token', 'content': limit_msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'citations', 'citations': []}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            rate_limit_stream(),
            media_type="text/event-stream",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "Retry-After": str(retry_after)
            }
        )

    history_dicts = [{"role": h.role, "content": h.content} for h in payload.history] if payload.history else []

    # 4. Gate 3: Anti-Prompting Attack & Abuse Gate (0 Tokens!)
    safety_check = inspect_query_safety(payload.query, history=history_dicts)

    if not safety_check.is_safe:
        strike_result = strike_manager.record_strike(
            ip=client_ip,
            subnet=subnet,
            device_id=device_id,
            mac=client_mac,
            user_agent=user_agent,
            query=payload.query,
            violation_type=safety_check.violation_type or "ABUSE",
            reason=safety_check.violation_reason or "Consulta fuera del ámbito universitario",
            db=db
        )
        strike_msg = strike_result["message"]

        def strike_stream():
            words = strike_msg.split(" ")
            for i, w in enumerate(words):
                chunk = w if i == len(words) - 1 else w + " "
                yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'citations', 'citations': []}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        resp_status = status.HTTP_403_FORBIDDEN if strike_result["is_banned"] else status.HTTP_200_OK
        return StreamingResponse(
            strike_stream(),
            media_type="text/event-stream",
            status_code=resp_status,
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "X-Security-Strike": str(strike_result["strike_count"]),
                "X-Security-Banned": "true" if strike_result["is_banned"] else "false"
            }
        )

    # 5. Gate 4: Fast Greeting & Orientation (0 Tokens!)
    if safety_check.is_greeting and safety_check.direct_response:
        def greeting_stream():
            words = safety_check.direct_response.split(" ")
            for i, w in enumerate(words):
                chunk = w if i == len(words) - 1 else w + " "
                yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'citations', 'citations': []}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            greeting_stream(),
            media_type="text/event-stream",
            status_code=status.HTTP_200_OK,
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )

    # 5. Gate 5: Hybrid Cache Check (Exact O(1) & Semantic >= 0.95) (0 Tokens!)
    cached_entry = redis_cache.get(payload.query)
    if cached_entry:
        cached_answer = cached_entry.get("answer", "")
        cached_citations = cached_entry.get("citations", [])
        cached_topic = cached_entry.get("topic") or classify_topic(payload.query)
        cache_layer = cached_entry.get("cache_layer", "exact")

        def cached_stream():
            try:
                words = cached_answer.split(" ")
                for i, w in enumerate(words):
                    chunk = w if i == len(words) - 1 else w + " "
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'citations', 'citations': cached_citations}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                db_log = None
                try:
                    db_log = SessionLocal()
                    log = StudentQueryLog(
                        query_text=payload.query,
                        topic_category=cached_topic,
                        citations_count=len(cached_citations),
                        confidence_score=1.0 if len(cached_citations) >= 2 else 0.85,
                        has_knowledge_gap=(len(cached_citations) == 0),
                        device_type="desktop"
                    )
                    db_log.add(log)
                    db_log.commit()
                except Exception as log_err:
                    print(f"[ChatLogCache] Error logging cached query: {log_err}")
                finally:
                    if db_log:
                        db_log.close()

        return StreamingResponse(
            cached_stream(),
            media_type="text/event-stream",
            status_code=status.HTTP_200_OK,
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "X-Cache-Hit": "true",
                "X-Cache-Layer": cache_layer
            }
        )

    # 6. Concurrency Limiter: Protect system against concurrent stream exhaustion (>150 streams)
    sem = getattr(security_guardrails, "STREAM_CONCURRENCY_SEMAPHORE", STREAM_CONCURRENCY_SEMAPHORE)
    acquired = sem.acquire(blocking=False)
    if not acquired:
        def busy_stream():
            msg = "⚠️ El sistema se encuentra atendiendo un volumen muy alto de consultas simultáneas. Por favor reintenta en unos instantes."
            yield f"data: {json.dumps({'type': 'token', 'content': msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'citations', 'citations': []}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(
            busy_stream(),
            media_type="text/event-stream",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers={"Retry-After": "5"}
        )

    guard = SemaphoreReleaseGuard(sem)

    def event_generator():
        citation_count = 0
        collected_tokens = []
        collected_citations = []
        stream_success = False
        stream_had_error_event = False

        q: queue.Queue = queue.Queue()
        stop_worker = threading.Event()

        def stream_worker():
            try:
                try:
                    stream_iter = rag_service.answer_stream(payload.query, history_dicts, emit_heartbeat=True)
                except TypeError:
                    stream_iter = rag_service.answer_stream(payload.query, history_dicts)
                for event in stream_iter:
                    if stop_worker.is_set():
                        break
                    q.put(("event", event))
                q.put(("done", None))
            except BaseException as exc:
                q.put(("error", exc))

        worker_thread = threading.Thread(target=stream_worker, daemon=True)
        worker_thread.start()

        keepalive_interval = float(getattr(settings, "SSE_KEEPALIVE_INTERVAL_SECONDS", 15.0))
        if keepalive_interval <= 0:
            keepalive_interval = 15.0

        try:
            while True:
                try:
                    msg_type, item = q.get(timeout=keepalive_interval)
                except queue.Empty:
                    # Keep connection alive across intermediary proxies (Cloudflare, Vercel Edge)
                    yield ": ping\n\n"
                    continue

                if msg_type == "done":
                    stream_success = True
                    yield "data: [DONE]\n\n"
                    break
                elif msg_type == "error":
                    raise item
                elif msg_type == "event":
                    event = item
                    if event.get("type") == "ping":
                        yield ": ping\n\n"
                        continue
                    if event.get("is_error"):
                        stream_had_error_event = True
                    if event.get("type") == "token":
                        collected_tokens.append(event.get("content", ""))
                    elif event.get("type") == "citations":
                        collected_citations = event.get("citations", [])
                        citation_count = len(collected_citations)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except GeneratorExit:
            stop_worker.set()
            raise
        except Exception as stream_err:
            logger.error(f"[ChatStream] Streaming exception: {stream_err}")
            err_msg = f"\n\n*(Error temporal en la transmisión: {str(stream_err)})*"
            yield f"data: {json.dumps({'type': 'token', 'content': err_msg}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            stop_worker.set()
            guard.release()
            db_log = None
            try:
                full_text = "".join(collected_tokens).lower()
                system_error_markers = [
                    "*(conexión interrumpida",
                    "*(conexion interrumpida",
                    "[error de comunicación con el modelo",
                    "[error de comunicacion con el modelo",
                    "*(error temporal durante la generación",
                    "*(error temporal durante la generacion",
                    "*(error temporal en la transmisión",
                    "*(error temporal en la transmision",
                ]
                has_system_marker = any(
                    marker in token.lower()
                    for token in collected_tokens
                    for marker in system_error_markers
                )
                has_stream_error = (not stream_success) or stream_had_error_event or has_system_marker

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
                if has_stream_error:
                    has_gap = True
                    confidence = 0.0
                elif is_other:
                    has_gap = False
                    confidence = 1.0
                else:
                    has_gap = (citation_count == 0) or any(phrase in full_text for phrase in gap_phrases)
                    confidence = 0.25 if (citation_count == 0) else (0.45 if has_gap else (1.0 if citation_count >= 2 else 0.85))

                db_log = SessionLocal()
                log = StudentQueryLog(
                    query_text=payload.query,
                    topic_category=classify_topic(payload.query),
                    citations_count=citation_count,
                    confidence_score=confidence,
                    has_knowledge_gap=has_gap,
                    device_type="desktop"
                )
                db_log.add(log)
                db_log.commit()
            except Exception as log_err:
                logger.error(f"[ChatLog] Error logging query: {log_err}")
            finally:
                if db_log:
                    db_log.close()

            # Store result in cache asynchronously in background on successful completion
            if stream_success and collected_tokens:
                full_answer = "".join(collected_tokens)
                if full_answer.strip() and not has_stream_error:
                    topic_cat = classify_topic(payload.query)
                    _submit_cache_write(payload.query, full_answer, collected_citations, topic_cat)

    gen = event_generator()

    response = StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "X-Cache-Hit": "false"
        }
    )
    response._release_guard = guard
    if hasattr(response, "body_iterator"):
        try:
            response.body_iterator._release_guard = guard
        except AttributeError:
            pass

    return response

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
def submit_session_feedback(
    request: Request,
    payload: SessionFeedbackPayload,
    db: Session = Depends(get_db)
):
    """
    Receives student feedback for a specific chat session, optionally including
    the transcript of the conversation, destined for canigraduateud@gmail.com.
    Rate limited to max 5 feedback submissions per minute.
    """
    client_info = extract_client_info(request)
    is_limited, retry_after = rate_limiter.is_rate_limited(
        endpoint_key="feedback",
        client_key=client_info["ip"],
        max_requests=5,
        window_seconds=60
    )
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Has superado el límite de envíos de feedback. Por favor espera {retry_after} segundos."
        )

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


