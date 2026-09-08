import os
import re
import email
import logging
from email.header import decode_header
from typing import List, Dict, Any, Tuple
from app.core.config import settings

logger = logging.getLogger(__name__)

def _decode_mime_words(s: str) -> str:
    """Decodes MIME encoded subject or header strings."""
    if not s:
        return ""
    try:
        decoded_fragments = decode_header(s)
        result = []
        for fragment, encoding in decoded_fragments:
            if isinstance(fragment, bytes):
                result.append(fragment.decode(encoding or "utf-8", errors="replace"))
            else:
                result.append(str(fragment))
        return "".join(result)
    except Exception as e:
        logger.warning(f"Error decoding MIME header '{s}': {e}")
        return str(s)

def _extract_body_and_attachments(msg: email.message.Message) -> Tuple[str, List[str]]:
    """Extracts text content and saves attached files (PDF, docx, etc.) to the uploads directory."""
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
                    # Clean filename safely
                    clean_name = re.sub(r'[^\w\.-]', '_', os.path.basename(filename))
                    file_path = os.path.join(upload_dir, clean_name)
                    payload = part.get_payload(decode=True)
                    if payload:
                        with open(file_path, "wb") as f:
                            f.write(payload)
                        saved_attachments.append(clean_name)
                        logger.info(f"Saved attached document from EML: {clean_name}")
            elif content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    body_parts.append(payload.decode("utf-8", errors="replace"))
            elif content_type == "text/html" and not body_parts and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    raw_html = payload.decode("utf-8", errors="replace")
                    # Clean tags and normalize spaces
                    clean_text = re.sub(r'<[^>]+>', ' ', raw_html)
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                    body_parts.append(clean_text)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body_parts.append(payload.decode("utf-8", errors="replace"))

    full_body = "\n\n".join(part.strip() for part in body_parts if part.strip()).strip()
    return full_body, saved_attachments

def _detect_original_sender(from_header: str, body: str) -> str:
    """
    If the email was forwarded or relayed by Outlook/Gmail, extracts the
    original faculty sender address (e.g. ingsistemas@udistrital.edu.co).
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

    # Match raw email in De: line
    simple_match = re.search(r'(?:De|From):\s*([a-zA-Z0-9_.+-]+@udistrital\.edu\.co)', body, re.IGNORECASE)
    if simple_match:
        return simple_match.group(1).strip()

    # Extract email within brackets if present in From header
    header_email_match = re.search(r'<([^>]+)>', decoded_from)
    if header_email_match:
        return header_email_match.group(1).strip()

    return decoded_from.strip()

def parse_eml_bytes(content: bytes) -> Dict[str, Any]:
    """
    Parses a raw .eml RFC822 file content and returns structured metadata,
    extracted body, attachments, and URLs.
    """
    msg = email.message_from_bytes(content)

    raw_subject = msg.get("Subject", "Comunicado Oficial Sin Asunto")
    subject = _decode_mime_words(raw_subject).strip()

    from_hdr = msg.get("From", "coordinacion_sistemas@udistrital.edu.co")
    date_hdr = msg.get("Date", "")

    body_text, attachments = _extract_body_and_attachments(msg)
    real_sender = _detect_original_sender(from_hdr, body_text)

    # Detect URLs in body
    detected_urls = list(set(re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', body_text)))[:5]

    return {
        "subject": subject or "Comunicado Oficial",
        "sender": real_sender,
        "date_header": date_hdr,
        "body": body_text,
        "attachments": attachments,
        "urls": detected_urls
    }

