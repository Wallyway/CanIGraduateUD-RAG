import json
from typing import List, Dict, Optional
from pydantic import BaseModel
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.services.rag_service import rag_service

router = APIRouter()

class ChatTurn(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    query: str
    history: Optional[List[ChatTurn]] = []

from app.db.session import SessionLocal
from app.db.models import StudentQueryLog

def classify_topic(query: str) -> str:
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
        for event in rag_service.answer_stream(payload.query, history_dicts):
            if event.get("type") == "citations":
                citation_count = len(event.get("citations", []))
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        try:
            db = SessionLocal()
            log = StudentQueryLog(
                query_text=payload.query,
                topic_category=classify_topic(payload.query),
                citations_count=citation_count,
                confidence_score=1.0 if citation_count > 0 else 0.35,
                has_knowledge_gap=(citation_count == 0),
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


