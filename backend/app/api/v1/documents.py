import os
import shutil
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.db.models import DocumentItem
from app.api.deps import get_current_admin
from app.services.document_processor import document_processor
from app.services.vector_store import vector_store
from app.services.markdown_converter import markdown_converter

router = APIRouter()

class SearchTestPayload(BaseModel):
    query: str
    limit: Optional[int] = 5

class DeprecatePayload(BaseModel):
    reason: Optional[str] = "Derogado por nueva normativa"
    superseded_by_title: Optional[str] = None

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

    doc_title = title or os.path.splitext(filename)[0].replace("_", " ").title()

    # Convert PDF to Markdown if PDF
    markdown_text = ""
    detected_derogations = []
    if ext == ".pdf":
        try:
            conv_result = markdown_converter.convert_pdf_to_markdown(file_path, doc_title)
            markdown_text = conv_result.get("markdown", "")
            detected_derogations = conv_result.get("detected_derogations", [])
        except Exception as conv_err:
            print(f"[Upload] Markdown conversion warning: {conv_err}")
            markdown_text = document_processor.extract_text_from_file(file_path)
    else:
        markdown_text = document_processor.extract_text_from_file(file_path)

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

    doc_item = DocumentItem(
        title=doc_title,
        filename=filename,
        file_path=file_path,
        file_type=ext.replace(".", ""),
        source_type="MANUAL_UPLOAD",
        resolution_number=resolution_number or "Resolución Institucional",
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
    """Deletes a document completely from the database and ChromaDB."""
    doc = db.query(DocumentItem).filter(DocumentItem.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    try:
        vector_store.delete_by_document_id(document_id)
    except Exception:
        pass

    db.delete(doc)
    db.commit()

    return {
        "success": True,
        "message": f"Documento #{document_id} eliminado de la base de datos."
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

    if doc.file_path and os.path.exists(doc.file_path):
        media_type = "application/pdf" if doc.file_path.endswith(".pdf") else "text/plain; charset=utf-8"
        return FileResponse(
            doc.file_path,
            media_type=media_type,
            filename=doc.filename,
            headers={"Content-Disposition": f"inline; filename=\"{doc.filename}\""}
        )

    # Fallback to returning markdown content as text
    if doc.markdown_content:
        return PlainTextResponse(doc.markdown_content, media_type="text/markdown; charset=utf-8")

    raise HTTPException(status_code=404, detail="El archivo fuente no está disponible en el servidor.")
