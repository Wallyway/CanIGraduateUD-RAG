import os
import re
import email
import imaplib
import asyncio
import logging
from email.header import decode_header
from typing import List, Dict, Any, Optional, Tuple
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.triage_service import triage_service

logger = logging.getLogger(__name__)

def _decode_mime_words(s: str) -> str:
    """Decodes MIME encoded subject or header strings."""
    if not s:
        return ""
    decoded_fragments = decode_header(s)
    result = []
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            result.append(fragment.decode(encoding or "utf-8", errors="replace"))
        else:
            result.append(str(fragment))
    return "".join(result)

def _extract_body_and_attachments(msg: email.message.Message) -> Tuple[str, List[str]]:
    """Extracts text content and saves attached PDFs to uploads directory."""
    body_parts = []
    saved_attachments = []
    upload_dir = os.path.join(settings.DATA_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Attachment handling
            if "attachment" in content_disposition or part.get_filename():
                raw_filename = part.get_filename()
                if raw_filename:
                    filename = _decode_mime_words(raw_filename)
                    # Clean filename
                    clean_name = re.sub(r'[^\w\.-]', '_', os.path.basename(filename))
                    file_path = os.path.join(upload_dir, clean_name)
                    payload = part.get_payload(decode=True)
                    if payload:
                        with open(file_path, "wb") as f:
                            f.write(payload)
                        saved_attachments.append(clean_name)
                        logger.info(f"Saved attached document: {clean_name}")
            elif content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    body_parts.append(payload.decode("utf-8", errors="replace"))
            elif content_type == "text/html" and not body_parts and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    raw_html = payload.decode("utf-8", errors="replace")
                    # Simple tag strip
                    clean_text = re.sub(r'<[^>]+>', ' ', raw_html)
                    body_parts.append(clean_text)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body_parts.append(payload.decode("utf-8", errors="replace"))

    full_body = "\n\n".join(body_parts).strip()
    return full_body, saved_attachments

def _detect_original_sender(from_header: str, body: str) -> str:
    """
    If the email was forwarded by Outlook Web, extract the original
    faculty sender address (e.g. ingsistemas@udistrital.edu.co).
    """
    decoded_from = _decode_mime_words(from_header)

    # Check if the body contains a forward header block
    # e.g.: "De: Proyecto Curricular <ingsistemas@udistrital.edu.co>" or "From: ..."
    forward_match = re.search(
        r'(?:De|From):\s*([^<\n\r]+)?<([^>\n\r@]+@[^>\n\r]+)>',
        body,
        re.IGNORECASE
    )
    if forward_match:
        original_email = forward_match.group(2).strip()
        logger.info(f"Detected forwarded original university sender: {original_email}")
        return original_email

    # Alternatively match raw email in De: line
    simple_match = re.search(r'(?:De|From):\s*([a-zA-Z0-9_.+-]+@udistrital\.edu\.co)', body, re.IGNORECASE)
    if simple_match:
        return simple_match.group(1).strip()

    return decoded_from

class IMAPListenerService:
    def __init__(self):
        self._is_running = False

    def check_emails_now(self) -> Dict[str, Any]:
        """
        Polls the IMAP inbox for unread (UNSEEN) emails,
        downloads, triages and indexes them.
        """
        if not settings.IMAP_ENABLED or not settings.IMAP_USER or not settings.IMAP_PASSWORD:
            return {
                "success": False,
                "message": "Servicio IMAP deshabilitado o credenciales no configuradas en .env",
                "processed": 0
            }

        processed_count = 0
        try:
            # Connect with SSL
            mail = imaplib.IMAP4_SSL(settings.IMAP_SERVER, settings.IMAP_PORT)
            mail.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
            mail.select("INBOX")

            # Search for unread emails
            status, response = mail.search(None, "UNSEEN")
            if status != "OK" or not response or not response[0]:
                mail.logout()
                return {"success": True, "message": "No hay correos nuevos sin leer.", "processed": 0}

            email_ids = response[0].split()
            logger.info(f"Found {len(email_ids)} new unread emails in {settings.IMAP_USER}")

            db = SessionLocal()
            try:
                for e_id in email_ids:
                    status, data = mail.fetch(e_id, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    raw_subject = msg.get("Subject", "Sin Asunto")
                    subject = _decode_mime_words(raw_subject)
                    from_hdr = msg.get("From", settings.IMAP_USER)
                    
                    body_text, attachments = _extract_body_and_attachments(msg)
                    real_sender = _detect_original_sender(from_hdr, body_text)

                    logger.info(f"Processing email: '{subject}' from {real_sender}")

                    # Run triage and ingest
                    email_record = triage_service.process_incoming_email(
                        db=db,
                        sender=real_sender,
                        subject=subject,
                        body=body_text,
                        attachments=attachments
                    )

                    processed_count += 1

                    # Mark email as read / seen
                    mail.store(e_id, "+FLAGS", "\\Seen")

                db.commit()
            finally:
                db.close()

            mail.close()
            mail.logout()

            return {
                "success": True,
                "message": f"Se procesaron e ingresaron {processed_count} comunicados correctamente.",
                "processed": processed_count
            }

        except Exception as e:
            logger.error(f"Error checking IMAP emails: {e}")
            return {
                "success": False,
                "message": f"Error al conectar con el servidor IMAP: {str(e)}",
                "processed": processed_count
            }

    async def background_loop(self):
        """Asynchronous background loop to poll IMAP periodically."""
        self._is_running = True
        logger.info(f"IMAP background listener started. Polling every {settings.IMAP_POLL_INTERVAL_SECONDS}s.")
        
        while self._is_running:
            try:
                if settings.IMAP_ENABLED and settings.IMAP_PASSWORD:
                    # Run sync blocking code in threadpool
                    await asyncio.to_thread(self.check_emails_now)
            except Exception as e:
                logger.error(f"Error in IMAP background listener: {e}")
            
            await asyncio.sleep(settings.IMAP_POLL_INTERVAL_SECONDS)

    def stop(self):
        self._is_running = False

imap_listener = IMAPListenerService()

