import smtplib
import logging
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailDispatcher:
    def __init__(self):
        pass

    def send_feedback_email(
        self,
        feedback_id: int,
        session_id: Optional[str],
        feedback_type: str,
        comments: str,
        rating: Optional[int] = None,
        user_email: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        target_email: str = "canigraduateud@gmail.com"
    ) -> Dict[str, Any]:
        """
        Dispatches an email containing session feedback to the target email.
        If SMTP credentials are configured in settings, it sends via smtplib.
        Otherwise, it logs and generates web compose & mailto links.
        """
        smtp_user = getattr(settings, "SMTP_USER", "") or ""
        smtp_password = getattr(settings, "SMTP_PASSWORD", "") or ""
        smtp_host = getattr(settings, "SMTP_HOST", "smtp.gmail.com") or "smtp.gmail.com"
        smtp_port = getattr(settings, "SMTP_PORT", 587) or 587
        from_email = getattr(settings, "SMTP_FROM_EMAIL", "") or smtp_user or "noreply@udistrital.edu.co"

        type_labels = {
            "sugerencia": "Sugerencia de Mejora",
            "informacion_imprecisa": "Información Imprecisa o Faltante",
            "error_tecnico": "Error o Problema Técnico",
            "general": "Comentario General"
        }
        type_label = type_labels.get(feedback_type, feedback_type.capitalize() if feedback_type else "General")
        subject = f"[Feedback CanIGraduateUD] {type_label}: Sesión {session_id or feedback_id}"

        # Plain text version
        body_lines = [
            "REPORTE DE FEEDBACK DE SESIÓN - CAN I GRADUATE UD",
            "=" * 50,
            f"Tipo: {type_label}",
            f"ID de Sesión: {session_id or feedback_id}",
            f"Calificación: {'★' * rating if rating else 'No indicada'}",
            f"Remitente / Contacto: {user_email or 'Anónimo (No especificado)'}",
            f"Destinatario oficial: {target_email}",
            "",
            "COMENTARIOS / OBSERVACIONES:",
            comments.strip(),
            ""
        ]

        if messages:
            body_lines.append("TRANSCRIPCIÓN COMPLETA DE LA SESIÓN:")
            body_lines.append("-" * 50)
            for idx, m in enumerate(messages, 1):
                role_label = "Estudiante" if m.get("role") == "user" else "Can I Graduate AI"
                body_lines.append(f"[{idx}] {role_label}:")
                body_lines.append(m.get("content", ""))
                body_lines.append("")

        text_content = "\n".join(body_lines)

        # HTML formatted version
        html_stars = ("★" * rating + "☆" * (5 - rating)) if rating else "No calificada"
        transcript_html_items = []
        if messages:
            for idx, m in enumerate(messages, 1):
                is_user = m.get("role") == "user"
                bg_color = "#f3f4f6" if is_user else "#fffbeb"
                border_color = "#e5e7eb" if is_user else "#fde68a"
                role_name = "Estudiante" if is_user else "Can I Graduate AI"
                content_escaped = (m.get("content", "") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
                transcript_html_items.append(f"""
                <div style="margin-bottom: 12px; padding: 12px; background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 8px;">
                    <div style="font-weight: bold; font-size: 12px; color: #4b5563; margin-bottom: 4px;">{idx}. {role_name}</div>
                    <div style="font-size: 13px; color: #1f2937; line-height: 1.5;">{content_escaped}</div>
                </div>
                """)

        transcript_html = "".join(transcript_html_items) if transcript_html_items else "<p style='color: #6b7280; font-style: italic;'>No se adjuntó transcripción.</p>"

        comments_escaped = comments.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"/></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f9fafb; padding: 20px; color: #111827;">
            <div style="max-width: 640px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
                <div style="background-color: #c2410c; padding: 16px 20px; color: #ffffff;">
                    <h2 style="margin: 0; font-size: 18px; font-weight: 700;">Can I Graduate UD - Feedback de Sesión</h2>
                    <p style="margin: 4px 0 0 0; font-size: 12px; opacity: 0.9;">Reporte de usuario para auditoría y mejora continua</p>
                </div>
                <div style="padding: 20px;">
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 13px;">
                        <tr><td style="padding: 6px 0; color: #6b7280; width: 140px;"><strong>Tipo de feedback:</strong></td><td style="padding: 6px 0; font-weight: 600;">{type_label}</td></tr>
                        <tr><td style="padding: 6px 0; color: #6b7280;"><strong>ID de Sesión:</strong></td><td style="padding: 6px 0; font-family: monospace;">{session_id or feedback_id}</td></tr>
                        <tr><td style="padding: 6px 0; color: #6b7280;"><strong>Calificación:</strong></td><td style="padding: 6px 0; color: #d97706; font-size: 15px;">{html_stars}</td></tr>
                        <tr><td style="padding: 6px 0; color: #6b7280;"><strong>Contacto estudiante:</strong></td><td style="padding: 6px 0;">{user_email or 'No especificado'}</td></tr>
                    </table>

                    <div style="margin-bottom: 20px;">
                        <h3 style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; border-bottom: 2px solid #fed7aa; padding-bottom: 4px;">Comentarios del Estudiante</h3>
                        <div style="background-color: #fff7ed; border: 1px solid #ffedd5; padding: 12px; border-radius: 8px; font-size: 14px; line-height: 1.6; color: #7c2d12;">
                            {comments_escaped}
                        </div>
                    </div>

                    <div>
                        <h3 style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; border-bottom: 2px solid #e5e7eb; padding-bottom: 4px;">Transcripción de la Conversación</h3>
                        {transcript_html}
                    </div>
                </div>
                <div style="background-color: #f3f4f6; padding: 12px 20px; font-size: 11px; color: #6b7280; text-align: center; border-top: 1px solid #e5e7eb;">
                    Can I Graduate UD • Sistema RAG de Normativa de Grado • Facultad de Ingeniería UD
                </div>
            </div>
        </body>
        </html>
        """

        # Preformatted links
        encoded_subject = urllib.parse.quote(subject)
        encoded_body = urllib.parse.quote(text_content[:3500])
        mailto_url = f"mailto:{target_email}?subject={encoded_subject}&body={encoded_body}"
        gmail_compose_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={target_email}&su={encoded_subject}&body={encoded_body}"

        # Attempt sending via SMTP if configured
        sent = False
        send_error = None

        if smtp_user and smtp_password:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = from_email
                msg["To"] = target_email
                if user_email and "@" in user_email:
                    msg["Reply-To"] = user_email

                part1 = MIMEText(text_content, "plain", "utf-8")
                part2 = MIMEText(html_content, "html", "utf-8")
                msg.attach(part1)
                msg.attach(part2)

                server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
                if getattr(settings, "SMTP_TLS", True):
                    server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(from_email, [target_email], msg.as_string())
                server.quit()

                sent = True
                logger.info(f"[EmailDispatcher] Feedback #{feedback_id} successfully sent via SMTP to {target_email}")
            except Exception as e:
                send_error = str(e)
                logger.error(f"[EmailDispatcher] Failed to send email via SMTP: {e}")
        else:
            logger.info(f"[EmailDispatcher] SMTP credentials not set. Email logged locally in database for {target_email}.")

        return {
            "sent": sent,
            "error": send_error,
            "has_smtp_configured": bool(smtp_user and smtp_password),
            "target_email": target_email,
            "subject": subject,
            "mailto_url": mailto_url,
            "gmail_compose_url": gmail_compose_url
        }

email_dispatcher = EmailDispatcher()

