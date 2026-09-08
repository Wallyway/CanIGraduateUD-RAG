import re
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import verify_webhook_token
from app.services.triage_service import triage_service

router = APIRouter()

class InboundEmailPayload(BaseModel):
    sender: str
    recipient: Optional[str] = "estudiante_sistemas@udistrital.edu.co"
    subject: str
    body: str
    attachments: Optional[List[str]] = []
    urls: Optional[List[str]] = []

@router.post("/incoming-email")
def receive_incoming_email(
    payload: InboundEmailPayload,
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_webhook_token)
):
    """
    Webhook endpoint to receive institutional emails forwarded by Microsoft Power Automate
    or institutional email rules without requiring Microsoft Entra ID tenant registration.
    """
    # Auto-extract URLs from body if not explicitly provided
    detected_urls = list(payload.urls or [])
    if not detected_urls:
        found = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', payload.body)
        detected_urls = list(set(found))[:5]

    email_record = triage_service.process_incoming_email(
        db=db,
        sender=payload.sender,
        subject=payload.subject,
        body=payload.body,
        attachments=payload.attachments,
        urls=detected_urls
    )

    return {
        "success": True,
        "email_id": email_record.id,
        "status": email_record.status,
        "is_relevant": email_record.is_relevant,
        "relevance_score": email_record.relevance_score,
        "triage_summary": email_record.triage_summary
    }

