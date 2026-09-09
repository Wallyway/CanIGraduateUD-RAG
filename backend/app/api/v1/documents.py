import os
import json
import shutil
import logging
from typing import List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, PlainTextResponse, HTMLResponse
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.db.models import DocumentItem, EmailNotice
from app.api.deps import get_current_admin
from app.services.document_processor import document_processor
from app.services.vector_store import vector_store
from app.services.markdown_converter import markdown_converter
from app.services.normative_auditor import normative_auditor

router = APIRouter()

class CreateMarkdownDocPayload(BaseModel):
    title: str
    content: str
    resolution_number: Optional[str] = None
    effective_date: Optional[str] = None
    supersedes_id: Optional[int] = None

class SearchTestPayload(BaseModel):
    query: str
    limit: Optional[int] = 5

class DeprecatePayload(BaseModel):
    reason: Optional[str] = "Derogado por nueva normativa"
    superseded_by_title: Optional[str] = None

def render_markdown_document_html(doc: DocumentItem, markdown_text: str) -> str:
    from markdown_it import MarkdownIt
    md = MarkdownIt("commonmark", {"breaks": True, "html": False})
    rendered_body = md.render(markdown_text)

    status_color = "#059669" if doc.validity_status == "VIGENTE" else ("#d97706" if doc.validity_status == "MODIFICADO" else "#dc2626")
    status_bg = "#ecfdf5" if doc.validity_status == "VIGENTE" else ("#fffbeb" if doc.validity_status == "MODIFICADO" else "#fef2f2")
    status_border = "#a7f3d0" if doc.validity_status == "VIGENTE" else ("#fde68a" if doc.validity_status == "MODIFICADO" else "#fecaca")
    status_label = doc.validity_status or "VIGENTE"

    title_escaped = (doc.title or "Documento Oficial").replace("<", "&lt;").replace(">", "&gt;")
    res_escaped = (doc.resolution_number or "Resolución Institucional").replace("<", "&lt;").replace(">", "&gt;")
    date_escaped = (doc.effective_date or "").replace("<", "&lt;").replace(">", "&gt;")
    date_html = f'<span>• <strong>Vigencia:</strong> {date_escaped}</span>' if date_escaped else ''

    scan_section_html = ""
    if doc.scan_image_path:
        scan_real = doc.scan_image_path
        if not os.path.exists(scan_real):
            possible = os.path.join(settings.DATA_DIR, "uploads", os.path.basename(scan_real))
            if os.path.exists(possible):
                scan_real = possible
        if os.path.exists(scan_real):
            scan_ext = os.path.splitext(scan_real)[1].lower()
            if scan_ext in [".png", ".jpg", ".jpeg", ".webp"]:
                scan_section_html = f"""
    <div style="margin: 24px 36px 0; padding: 16px 20px; background: #fff7ed; border: 1px solid #fed7aa; border-radius: 12px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
        <span style="font-weight: 700; color: #9a3412; font-size: 13px; display: flex; align-items: center; gap: 6px;">
          📷 Copia Escaneada Original de Respaldo
        </span>
        <div style="display: flex; gap: 8px;">
          <a href="/api/v1/documents/{doc.id}/scan" target="_blank" class="btn" style="background: #ffffff; font-size: 11px;">
            🔍 Abrir Escaneo en Tamaño Completo
          </a>
        </div>
      </div>
      <div style="text-align: center; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #fed7aa;">
        <a href="/api/v1/documents/{doc.id}/scan" target="_blank" title="Clic para abrir escaneo en alta resolución">
          <img src="/api/v1/documents/{doc.id}/scan" alt="Escaneo oficial del acuerdo" style="max-width: 100%; max-height: 550px; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); object-fit: contain; cursor: zoom-in;" />
        </a>
        <p style="font-size: 11px; color: #78716c; margin-top: 8px;">Imagen original adjunta del acuerdo institucional. Haz clic para ver en alta resolución.</p>
      </div>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title_escaped} | Can I Graduate UD</title>
  <style>
    :root {{
      --primary: #c2410c;
      --primary-dark: #9a3412;
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #1e293b;
      --text-muted: #64748b;
      --border: #e2e8f0;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.75;
      padding: 24px 16px 60px;
    }}
    .container {{
      max-width: 860px;
      margin: 0 auto;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.06);
      overflow: hidden;
    }}
    .header-bar {{
      background: linear-gradient(135deg, #18181b 0%, #27272a 100%);
      color: #fff;
      padding: 28px 32px;
      border-bottom: 3px solid var(--primary);
    }}
    .institution-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: #fed7aa;
      margin-bottom: 12px;
    }}
    .title {{
      font-size: 22px;
      font-weight: 700;
      color: #ffffff;
      line-height: 1.35;
      margin-bottom: 14px;
    }}
    .meta-row {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
      font-size: 13px;
      color: #cbd5e1;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 3px 10px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      background-color: {status_bg};
      color: {status_color};
      border: 1px solid {status_border};
    }}
    .toolbar {{
      background: #f1f5f9;
      padding: 12px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border);
      font-size: 13px;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      padding: 6px 14px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      color: var(--text);
      cursor: pointer;
      text-decoration: none;
      transition: all 0.15s ease;
    }}
    .btn:hover {{
      background: #f8fafc;
      border-color: #94a3b8;
    }}
    .btn-primary {{
      background: var(--primary);
      color: #ffffff;
      border-color: var(--primary);
    }}
    .btn-primary:hover {{
      background: var(--primary-dark);
    }}
    .content-body {{
      padding: 36px 36px 48px;
      font-size: 15px;
      color: #334155;
    }}
    .content-body h1, .content-body h2, .content-body h3 {{
      color: #0f172a;
      margin-top: 28px;
      margin-bottom: 12px;
      font-weight: 700;
      line-height: 1.3;
    }}
    .content-body h1 {{ font-size: 20px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
    .content-body h2 {{ font-size: 17px; }}
    .content-body h3 {{ font-size: 15px; }}
    .content-body p {{ margin-bottom: 14px; text-align: justify; }}
    .content-body ul, .content-body ol {{ margin: 12px 0 16px 24px; }}
    .content-body li {{ margin-bottom: 6px; }}
    .content-body table {{
      width: 100%;
      border-collapse: collapse;
      margin: 18px 0;
      font-size: 13px;
    }}
    .content-body th, .content-body td {{
      border: 1px solid var(--border);
      padding: 8px 12px;
      text-align: left;
    }}
    .content-body th {{ background: #f8fafc; font-weight: 600; }}
    .content-body blockquote {{
      border-left: 4px solid var(--primary);
      padding: 8px 16px;
      margin: 16px 0;
      background: #fff7ed;
      color: #7c2d12;
      border-radius: 0 8px 8px 0;
    }}
    .footer-note {{
      padding: 20px 36px;
      background: #f8fafc;
      border-top: 1px solid var(--border);
      font-size: 12px;
      color: var(--text-muted);
      text-align: center;
    }}
    @media print {{
      body {{ background: #ffffff; padding: 0; }}
      .container {{ border: none; box-shadow: none; max-width: 100%; }}
      .toolbar {{ display: none; }}
      .header-bar {{ background: #ffffff !important; color: #000000 !important; border-bottom: 2px solid #000; padding: 16px 0; }}
      .title {{ color: #000000 !important; }}
      .content-body {{ padding: 20px 0; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header-bar">
      <div class="institution-pill">
        Universidad Distrital Francisco José de Caldas • Facultad de Ingeniería
      </div>
      <h1 class="title">{title_escaped}</h1>
      <div class="meta-row">
        <span><strong>Resolución:</strong> {res_escaped}</span>
        {date_html}
        <span class="badge">{status_label}</span>
      </div>
    </div>

    <div class="toolbar">
      <span>Documento normativo indexado en Can I Graduate UD</span>
      <div style="display: flex; gap: 8px;">
        <button onclick="window.print()" class="btn btn-primary">🖨️ Imprimir / Guardar PDF</button>
        <button onclick="navigator.clipboard.writeText(document.querySelector('.content-body').innerText).then(() => alert('Texto copiado al portapapeles'))" class="btn">📋 Copiar Texto</button>
      </div>
    </div>

    {scan_section_html}

    <div class="content-body">
      {rendered_body}
    </div>

    <div class="footer-note">
      Documento oficial de consulta para Ingeniería de Sistemas • Sistema RAG Can I Graduate UD
    </div>
  </div>
</body>
</html>"""

@router.get("/")
def list_documents(
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Lists all indexed knowledge base documents with validity status and lineage."""
    docs = db.query(DocumentItem).order_by(DocumentItem.created_at.desc()).all()
    results = []
    for d in docs:
        results.append({
            "id": d.id,
            "title": d.title,
            "filename": d.filename,
            "file_type": d.file_type,
            "source_type": d.source_type,
            "resolution_number": d.resolution_number,
            "effective_date": d.effective_date,
            "chunk_count": d.chunk_count,
            "status": d.status,
            "validity_status": d.validity_status or "VIGENTE",
            "supersedes_id": d.supersedes_id,
            "superseded_by_title": d.superseded_by_title,
            "has_markdown": bool(d.markdown_content),
            "has_scan_image": bool(d.scan_image_path and (os.path.exists(d.scan_image_path) or os.path.exists(os.path.join(settings.DATA_DIR, "uploads", os.path.basename(d.scan_image_path))))),
            "scan_url": f"/api/v1/documents/{d.id}/scan" if d.scan_image_path else None,
            "original_pdf_url": d.original_pdf_url or f"/api/v1/documents/{d.id}/pdf",
            "created_at": d.created_at.isoformat() if d.created_at else None
        })
    return results

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    resolution_number: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    supersedes_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """
    Uploads a PDF resolution, automatically transforms it to clean Markdown,
    extracts derogation clauses, links lineage, and indexes into ChromaDB.
    """
    filename = file.filename or "uploaded_document"
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in [".pdf", ".md", ".txt"]:
        raise HTTPException(status_code=400, detail="Formato de archivo no soportado. Debe ser PDF, MD o TXT.")

    upload_dir = os.path.join(settings.DATA_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Convert PDF to Markdown if PDF
    markdown_text = ""
    detected_derogations = []
    if ext == ".pdf":
        try:
            conv_result = markdown_converter.convert_pdf_to_markdown(file_path, title)
            markdown_text = conv_result.get("markdown", "")
            detected_derogations = conv_result.get("detected_derogations", [])
        except Exception as conv_err:
            print(f"[Upload] Markdown conversion warning: {conv_err}")
            markdown_text = document_processor.extract_text_from_file(file_path)
    else:
        markdown_text = document_processor.extract_text_from_file(file_path)

    official_meta = document_processor.extract_official_metadata(markdown_text)
    doc_title = title or official_meta.get("title") or os.path.splitext(filename)[0].replace("_", " ").title()
    doc_resolution = resolution_number or official_meta.get("resolution_number") or "Resolución Institucional"

    applied_derogations = []
    # Check if this document supersedes an older document
    superseded_title = None
    if supersedes_id:
        older_doc = db.query(DocumentItem).filter(DocumentItem.id == supersedes_id).first()
        if older_doc:
            superseded_title = older_doc.title
            older_doc.validity_status = "DEROGADO"
            older_doc.superseded_by_title = doc_title
            # De-index older document from ChromaDB to prevent outdated advice
            try:
                vector_store.delete_by_document_id(supersedes_id)
                older_doc.chunk_count = 0
            except Exception as v_err:
                print(f"[Upload] Error de-indexing superseded doc: {v_err}")
    else:
        # Automatically audit derogations using the LLM normative auditor
        try:
            audit = normative_auditor.audit_derogations(markdown_text, doc_title, effective_date, db)
            if audit.get("has_derogation"):
                applied_derogations = normative_auditor.apply_derogations(audit, doc_title, db, min_confidence=85.0)
                if applied_derogations:
                    superseded_title = ", ".join([d.get("title", "") for d in applied_derogations])
                    if not supersedes_id:
                        supersedes_id = applied_derogations[0].get("document_id")
        except Exception as audit_err:
            print(f"[Upload] Warning in normative audit: {audit_err}")

    doc_item = DocumentItem(
        title=doc_title,
        filename=filename,
        file_path=file_path,
        file_type=ext.replace(".", ""),
        source_type="MANUAL_UPLOAD",
        resolution_number=doc_resolution,
        effective_date=effective_date,
        validity_status="VIGENTE",
        supersedes_id=supersedes_id,
        markdown_content=markdown_text,
        status="INDEXED"
    )
    db.add(doc_item)
    db.commit()
    db.refresh(doc_item)

    doc_item.original_pdf_url = f"/api/v1/documents/{doc_item.id}/pdf"
    db.commit()

    # Chunk and index markdown
    try:
        metadata = {
            "document_id": doc_item.id,
            "title": doc_item.title,
            "filename": doc_item.filename,
            "resolution_number": doc_item.resolution_number,
            "source_type": doc_item.source_type,
            "effective_date": doc_item.effective_date or "",
            "pdf_url": doc_item.original_pdf_url,
            "validity_status": "VIGENTE"
        }
        chunks, metas, ids = document_processor.chunk_normative_text(markdown_text, metadata)
        if chunks:
            vector_store.add_chunks(chunks, metas, ids)
            doc_item.chunk_count = len(chunks)
            db.commit()
    except Exception as e:
        doc_item.status = "ERROR"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Error al indexar el documento: {str(e)}")

    return {
        "success": True,
        "message": f"Documento '{doc_item.title}' transformado a Markdown e indexado exitosamente.",
        "document_id": doc_item.id,
        "chunks_indexed": doc_item.chunk_count,
        "detected_derogations": detected_derogations,
        "applied_derogations": applied_derogations,
        "superseded_document": superseded_title
    }

@router.post("/create-markdown")
async def create_markdown_document(
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """
    Creates and indexes a document directly from Markdown text,
    with an optional attached original scan/image file (.png, .jpg, .webp, .pdf).
    Ideal for agreements received as scanned image PDFs that were transcribed to Markdown.
    """
    content_type = request.headers.get("content-type", "")
    scan_file = None
    if "multipart/form-data" in content_type:
        form_data = await request.form()
        title = form_data.get("title", "")
        content = form_data.get("content", "")
        resolution_number = form_data.get("resolution_number")
        effective_date = form_data.get("effective_date")
        supersedes_id_val = form_data.get("supersedes_id")
        supersedes_id = int(supersedes_id_val) if supersedes_id_val and str(supersedes_id_val).isdigit() else None
        scan_file = form_data.get("scan_file")
    else:
        json_data = await request.json()
        title = json_data.get("title", "")
        content = json_data.get("content", "")
        resolution_number = json_data.get("resolution_number")
        effective_date = json_data.get("effective_date")
        supersedes_id = json_data.get("supersedes_id")

    if not content or len(content.strip()) < 10:
        raise HTTPException(status_code=400, detail="El contenido en Markdown no puede estar vacío.")

    markdown_text = content.strip()
    official_meta = document_processor.extract_official_metadata(markdown_text)

    doc_title = title.strip() or official_meta.get("title") or "Acuerdo Institucional"
    doc_resolution = resolution_number or official_meta.get("resolution_number") or "Acuerdo / Resolución Oficial"
    effective_date_val = effective_date or official_meta.get("effective_date")

    upload_dir = os.path.join(settings.DATA_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # Save optional scan/image file if provided
    scan_image_path = None
    has_pdf_scan = False
    if scan_file and hasattr(scan_file, "filename") and scan_file.filename:
        scan_ext = os.path.splitext(scan_file.filename)[1].lower()
        if scan_ext in [".png", ".jpg", ".jpeg", ".webp", ".pdf"]:
            safe_scan_name = re.sub(r'[^\w\.-]', '_', os.path.splitext(scan_file.filename)[0].lower())[:40]
            scan_filename = f"scan_{safe_scan_name}_{int(datetime.utcnow().timestamp())}{scan_ext}"
            scan_image_path = os.path.join(upload_dir, scan_filename)
            with open(scan_image_path, "wb") as buffer:
                shutil.copyfileobj(scan_file.file, buffer)
            if scan_ext == ".pdf":
                has_pdf_scan = True

    # Generate a clean filename for the Markdown version
    safe_title = re.sub(r'[^\w\.-]', '_', doc_title.lower())[:50]
    filename = f"{safe_title}_{int(datetime.utcnow().timestamp())}.md"
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)

    # Auditing derogations
    applied_derogations = []
    superseded_title = None

    if supersedes_id:
        older_doc = db.query(DocumentItem).filter(DocumentItem.id == supersedes_id).first()
        if older_doc:
            superseded_title = older_doc.title
            older_doc.validity_status = "DEROGADO"
            older_doc.superseded_by_title = doc_title
            try:
                vector_store.delete_by_document_id(supersedes_id)
                older_doc.chunk_count = 0
            except Exception as v_err:
                logger.warning(f"Error de-indexing superseded doc: {v_err}")
    else:
        try:
            audit = normative_auditor.audit_derogations(markdown_text, doc_title, effective_date_val, db)
            if audit.get("has_derogation"):
                applied_derogations = normative_auditor.apply_derogations(audit, doc_title, db, min_confidence=85.0)
                if applied_derogations:
                    superseded_title = ", ".join([d.get("title", "") for d in applied_derogations])
                    if not supersedes_id:
                        supersedes_id = applied_derogations[0].get("document_id")
        except Exception as audit_err:
            logger.warning(f"[CreateMarkdown] Warning in normative audit: {audit_err}")

    # If the user attached a physical PDF scan, point file_path directly to it
    doc_file_path = scan_image_path if (has_pdf_scan and scan_image_path) else file_path
    doc_file_type = "pdf" if has_pdf_scan else "md"
    doc_filename = os.path.basename(doc_file_path)

    doc_item = DocumentItem(
        title=doc_title,
        filename=doc_filename,
        file_path=doc_file_path,
        file_type=doc_file_type,
        source_type="MANUAL_UPLOAD",
        resolution_number=doc_resolution,
        effective_date=effective_date_val,
        validity_status="VIGENTE",
        supersedes_id=supersedes_id,
        markdown_content=markdown_text,
        scan_image_path=scan_image_path,
        status="INDEXED"
    )
    db.add(doc_item)
    db.commit()
    db.refresh(doc_item)

    doc_item.original_pdf_url = f"/api/v1/documents/{doc_item.id}/pdf"
    db.commit()

    # Chunk and index into ChromaDB
    try:
        metadata = {
            "document_id": doc_item.id,
            "title": doc_item.title,
            "filename": doc_item.filename,
            "resolution_number": doc_item.resolution_number,
            "source_type": doc_item.source_type,
            "effective_date": doc_item.effective_date or "",
            "pdf_url": doc_item.original_pdf_url,
            "validity_status": "VIGENTE"
        }
        chunks, metas, ids = document_processor.chunk_normative_text(markdown_text, metadata)
        if chunks:
            vector_store.add_chunks(chunks, metas, ids)
            doc_item.chunk_count = len(chunks)
            db.commit()
    except Exception as e:
        doc_item.status = "ERROR"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Error al indexar en base vectorial: {str(e)}")

    return {
        "success": True,
        "message": f"Documento '{doc_item.title}' indexado exitosamente en ChromaDB.",
        "document_id": doc_item.id,
        "chunks_indexed": doc_item.chunk_count,
        "applied_derogations": applied_derogations,
        "superseded_document": superseded_title
    }

@router.post("/{document_id}/deprecate")
def deprecate_document(
    document_id: int,
    payload: Optional[DeprecatePayload] = None,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Marks a document as DEROGADO and removes its active chunks from ChromaDB."""
    doc = db.query(DocumentItem).filter(DocumentItem.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    doc.validity_status = "DEROGADO"
    if payload and payload.superseded_by_title:
        doc.superseded_by_title = payload.superseded_by_title

    # Remove vector chunks from ChromaDB so RAG will no longer answer with this document
    try:
        vector_store.delete_by_document_id(document_id)
        doc.chunk_count = 0
    except Exception as e:
        print(f"[Deprecate] Warning deleting chunks: {e}")

    db.commit()
    return {
        "success": True,
        "message": f"Documento '{doc.title}' marcado como DEROGADO y desindexado de ChromaDB.",
        "document_id": doc.id,
        "validity_status": doc.validity_status
    }

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Deletes a document completely from the database, ChromaDB, and disk."""
    doc = db.query(DocumentItem).filter(DocumentItem.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Delete vector chunks from ChromaDB
    try:
        vector_store.delete_by_document_id(document_id)
        logger.info(f"Deleted vector chunks for document #{document_id} from ChromaDB.")
    except Exception as v_err:
        logger.warning(f"Error deleting vector chunks for #{document_id}: {v_err}")

    # Remove physical file if located in uploads directory
    if doc.file_path and os.path.exists(doc.file_path) and "/uploads/" in doc.file_path:
        try:
            os.remove(doc.file_path)
            logger.info(f"Removed uploaded file on disk: {doc.file_path}")
        except Exception as f_err:
            logger.warning(f"Could not remove file on disk {doc.file_path}: {f_err}")

    if doc.scan_image_path and os.path.exists(doc.scan_image_path) and "/uploads/" in doc.scan_image_path:
        try:
            os.remove(doc.scan_image_path)
            logger.info(f"Removed scan image file on disk: {doc.scan_image_path}")
        except Exception as s_err:
            logger.warning(f"Could not remove scan image file on disk {doc.scan_image_path}: {s_err}")

    # If document came from an email, ensure any paired email_body document has its chunks purged
    if doc.email_id:
        companion_docs = db.query(DocumentItem).filter(
            DocumentItem.email_id == doc.email_id,
            DocumentItem.id != document_id
        ).all()
        for comp in companion_docs:
            try:
                vector_store.delete_by_document_id(comp.id)
                comp.chunk_count = 0
            except Exception:
                pass

    doc_title = doc.title
    db.delete(doc)
    db.commit()

    return {
        "success": True,
        "message": f"Documento '{doc_title}' (#{document_id}) y sus vectores fueron eliminados permanentemente."
    }

@router.post("/test-search")
def test_semantic_search(
    payload: SearchTestPayload,
    db: Session = Depends(get_db),
    admin: str = Depends(get_current_admin)
):
    """Performs a live semantic query against ChromaDB and returns raw matching chunks."""
    results = vector_store.query(payload.query, n_results=payload.limit or 5)
    return {
        "query": payload.query,
        "matches_count": len(results),
        "results": results
    }

@router.get("/{document_id}/pdf")
def view_document_pdf(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Public endpoint for opening / previewing the original PDF or source document in a new browser tab.
    Used by student chat citations and admin document inspection.
    """
    doc = db.query(DocumentItem).filter(DocumentItem.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # 1. Resolve physical file path if any
    real_path = doc.file_path
    if (not real_path or not os.path.exists(real_path)) and doc.filename:
        possible_path = os.path.join(settings.DATA_DIR, "uploads", doc.filename)
        if os.path.exists(possible_path):
            real_path = possible_path

    # Check if doc has scan_image_path that is a PDF
    if (not real_path or not os.path.exists(real_path) or not real_path.lower().endswith(".pdf")) and doc.scan_image_path:
        scan_cand = doc.scan_image_path
        if not os.path.exists(scan_cand):
            scan_cand = os.path.join(settings.DATA_DIR, "uploads", os.path.basename(scan_cand))
        if os.path.exists(scan_cand) and scan_cand.lower().endswith(".pdf"):
            real_path = scan_cand

    # Check if doc is linked to an EmailNotice that has an attached PDF in uploads
    if (not real_path or not os.path.exists(real_path) or not real_path.lower().endswith(".pdf")) and doc.email_id:
        email = db.query(EmailNotice).filter(EmailNotice.id == doc.email_id).first()
        if email and email.attachment_paths:
            try:
                attachments = json.loads(email.attachment_paths) if email.attachment_paths.startswith("[") else [email.attachment_paths]
                for att in attachments:
                    if att.lower().endswith(".pdf"):
                        att_path = os.path.join(settings.DATA_DIR, "uploads", att)
                        if os.path.exists(att_path):
                            real_path = att_path
                            break
            except Exception:
                pass

    # If physical PDF exists on disk, serve as native application/pdf
    if real_path and os.path.exists(real_path) and real_path.lower().endswith(".pdf"):
        download_filename = os.path.basename(real_path)
        return FileResponse(
            real_path,
            media_type="application/pdf",
            filename=download_filename,
            headers={"Content-Disposition": f"inline; filename=\"{download_filename}\""}
        )

    # 2. Extract markdown / text content from doc, file, or paired email
    markdown_text = doc.markdown_content
    if not markdown_text and real_path and os.path.exists(real_path):
        try:
            with open(real_path, "r", encoding="utf-8") as f:
                markdown_text = f.read()
        except Exception:
            pass

    if not markdown_text and doc.email_id:
        email = db.query(EmailNotice).filter(EmailNotice.id == doc.email_id).first()
        if email and email.body_text:
            markdown_text = email.body_text
            try:
                doc.markdown_content = email.body_text
                db.commit()
            except Exception:
                pass

    # 3. Serve as beautifully formatted official HTML document
    if markdown_text and markdown_text.strip():
        html_page = render_markdown_document_html(doc, markdown_text)
        return HTMLResponse(content=html_page, media_type="text/html; charset=utf-8")

    raise HTTPException(status_code=404, detail="El archivo fuente no está disponible en el servidor.")

@router.get("/{document_id}/scan")
def view_document_scan(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Public endpoint to view or download the original scanned image or file
    attached to a manual markdown document.
    """
    doc = db.query(DocumentItem).filter(DocumentItem.id == document_id).first()
    if not doc or not doc.scan_image_path:
        raise HTTPException(status_code=404, detail="El documento no tiene una imagen o escaneo adjunto.")

    scan_path = doc.scan_image_path
    if not os.path.exists(scan_path):
        possible_path = os.path.join(settings.DATA_DIR, "uploads", os.path.basename(scan_path))
        if os.path.exists(possible_path):
            scan_path = possible_path
        else:
            raise HTTPException(status_code=404, detail="El archivo de escaneo no se encuentra en el servidor.")

    ext = os.path.splitext(scan_path)[1].lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".pdf": "application/pdf"
    }
    media_type = media_types.get(ext, "application/octet-stream")
    scan_filename = os.path.basename(scan_path)
    return FileResponse(
        scan_path,
        media_type=media_type,
        filename=scan_filename,
        headers={"Content-Disposition": f"inline; filename=\"{scan_filename}\""}
    )
