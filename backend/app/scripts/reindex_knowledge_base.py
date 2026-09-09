import os
import sys
import logging
from app.core.config import settings
from app.db.session import SessionLocal, init_db
from app.db.models import DocumentItem, EmailNotice
from app.services.document_processor import document_processor
from app.services.vector_store import vector_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reindexer")

def reindex_all():
    """
    Re-extracts and re-indexes all documents in SQLite and ChromaDB
    using layout extraction, running header suppression, and official metadata.
    """
    init_db()
    db = SessionLocal()
    try:
        documents = db.query(DocumentItem).all()
        logger.info(f"Found {len(documents)} documents to re-index.")

        total_reindexed = 0

        for doc in documents:
            logger.info(f"--- Processing Document ID {doc.id} ({doc.filename}) ---")
            
            raw_text = ""
            # Handle uploaded files or attachments on disk
            if doc.file_path and os.path.exists(doc.file_path):
                logger.info(f"Re-extracting text from file: {doc.file_path}")
                raw_text = document_processor.extract_text_from_file(doc.file_path)

                # Attempt official metadata discovery
                official_meta = document_processor.extract_official_metadata(raw_text)
                if official_meta.get("resolution_number"):
                    logger.info(f"Discovered official resolution: {official_meta['resolution_number']}")
                    doc.resolution_number = official_meta["resolution_number"]
                if official_meta.get("title") and ("Adjunto:" in doc.title or "ANEXO" in doc.title or doc.title == doc.filename):
                    logger.info(f"Updating title to: {official_meta['title']}")
                    doc.title = official_meta["title"]
                if official_meta.get("effective_date") and not doc.effective_date:
                    doc.effective_date = official_meta["effective_date"]

            elif doc.source_type == "EMAIL_BODY" and doc.email_id:
                email = db.query(EmailNotice).filter(EmailNotice.id == doc.email_id).first()
                if email and email.body_text:
                    # Check if email has attached documents that are already indexed
                    has_doc_attachments = False
                    if email.attachment_paths:
                        try:
                            import json
                            att_list = json.loads(email.attachment_paths)
                            has_doc_attachments = any(
                                os.path.splitext(a)[1].lower() in [".pdf", ".txt", ".md"]
                                for a in att_list
                            )
                        except Exception:
                            pass

                    # If this email has document attachments and body is long, avoid duplicate vectors
                    if has_doc_attachments and len(email.body_text.strip()) >= 2500:
                        logger.info(f"Purging redundant vector chunks for email body {doc.id} (canonical attached document will be indexed).")
                        vector_store.delete_by_document_id(doc.id)
                        doc.chunk_count = 0
                        db.commit()
                        continue

                    logger.info(f"Re-indexing email body for email ID {email.id}")
                    raw_text = email.body_text

            if not raw_text or not raw_text.strip():
                logger.warning(f"No text extracted for document ID {doc.id}, skipping vector upsert.")
                continue

            # Purge existing chunks in vector store
            try:
                vector_store.delete_by_document_id(doc.id)
                logger.info(f"Deleted previous chunks for document ID {doc.id} from ChromaDB.")
            except Exception as del_err:
                logger.warning(f"Error purging old chunks for doc {doc.id}: {del_err}")

            # Generate new structure-aware chunks with max_chunk_size=1800
            meta = {
                "document_id": doc.id,
                "title": doc.title,
                "filename": doc.filename,
                "resolution_number": doc.resolution_number or "",
                "source_type": doc.source_type or "NORMATIVA",
                "effective_date": doc.effective_date or "",
                "validity_status": doc.validity_status or "VIGENTE"
            }
            if doc.original_pdf_url:
                meta["pdf_url"] = doc.original_pdf_url

            chunks, metas, ids = document_processor.chunk_normative_text(raw_text, meta)
            if chunks:
                vector_store.add_chunks(chunks, metas, ids)
                doc.chunk_count = len(chunks)
                doc.markdown_content = raw_text
                db.commit()
                total_reindexed += 1
                logger.info(f"Successfully re-indexed {len(chunks)} chunks for '{doc.title}'.")
            else:
                logger.warning(f"Chunker produced 0 chunks for document ID {doc.id}!")

        total_chunks = vector_store.get_total_chunks()
        logger.info(f"Re-indexing complete! Total documents updated: {total_reindexed}. Total chunks in ChromaDB: {total_chunks}.")
    finally:
        db.close()

if __name__ == "__main__":
    reindex_all()

