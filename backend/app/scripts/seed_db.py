import os
import glob
import logging
from app.core.config import settings
from app.db.session import SessionLocal, init_db
from app.db.models import DocumentItem
from app.services.document_processor import document_processor
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)

DOC_METADATA_MAP = {
    "acuerdo_027_1993_estatuto_estudiantil.md": {
        "title": "Estatuto Estudiantil UD",
        "resolution_number": "Acuerdo No. 027 de 1993 CSU",
        "effective_date": "1993-12-24"
    },
    "acuerdo_038_2015_modalidades_grado_ingenieria.md": {
        "title": "Reglamento de Modalidades de Grado - Facultad de Ingeniería",
        "resolution_number": "Acuerdo No. 038 de 2015 Consejo de Facultad",
        "effective_date": "2015-10-15"
    },
    "acuerdo_004_2021_requisito_segunda_lengua_ilud.md": {
        "title": "Requisito de Segunda Lengua B2 / ILUD",
        "resolution_number": "Acuerdo No. 004 de 2021 Consejo Académico",
        "effective_date": "2021-03-18"
    },
    "procedimiento_paz_y_salvo_y_grados.md": {
        "title": "Guía de Trámites de Paz y Salvo y Ceremonias de Grado",
        "resolution_number": "Procedimiento Institucional Cóndor / Secretaría Académica",
        "effective_date": "2024-01-15"
    }
}

def seed_knowledge_base():
    """Indexes all seed normative documents from data/seed_documents into ChromaDB."""
    init_db()
    db = SessionLocal()
    try:
        seed_dir = os.path.join(settings.DATA_DIR, "seed_documents")
        if not os.path.exists(seed_dir):
            logger.info(f"Directory {seed_dir} does not exist. Skipping seed.")
            return

        files = glob.glob(os.path.join(seed_dir, "*.*"))
        indexed_count = 0

        for file_path in files:
            filename = os.path.basename(file_path)
            existing = db.query(DocumentItem).filter(DocumentItem.filename == filename).first()
            if existing and existing.chunk_count > 0 and vector_store.get_total_chunks() > 0:
                continue

            info = DOC_METADATA_MAP.get(filename, {
                "title": os.path.splitext(filename)[0].replace("_", " ").title(),
                "resolution_number": "Normativa Institucional UD",
                "effective_date": "2024-01-01"
            })

            logger.info(f"Processing seed document: {filename}...")
            raw_text = document_processor.extract_text_from_file(file_path)

            doc_item = existing or DocumentItem(
                title=info["title"],
                filename=filename,
                file_path=file_path,
                file_type=os.path.splitext(filename)[1].replace(".", ""),
                source_type="SEED",
                resolution_number=info["resolution_number"],
                effective_date=info["effective_date"],
                status="INDEXED"
            )
            if not existing:
                db.add(doc_item)
                db.commit()
                db.refresh(doc_item)

            meta = {
                "document_id": doc_item.id,
                "title": doc_item.title,
                "filename": doc_item.filename,
                "resolution_number": doc_item.resolution_number,
                "source_type": doc_item.source_type,
                "effective_date": doc_item.effective_date
            }

            chunks, metas, ids = document_processor.chunk_normative_text(raw_text, meta)
            if chunks:
                vector_store.add_chunks(chunks, metas, ids)
                doc_item.chunk_count = len(chunks)
                db.commit()
                indexed_count += 1
                logger.info(f"Indexed {len(chunks)} chunks for {filename}.")

        logger.info(f"Seed completed. Total seed documents newly indexed: {indexed_count}.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_knowledge_base()

