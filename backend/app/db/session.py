from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.db.models import Base, SystemSetting

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from sqlalchemy import text

def init_db():
    Base.metadata.create_all(bind=engine)
    # Safe column additions for SQLite if table already existed
    with engine.connect() as conn:
        for col_name, col_type in [
            ("validity_status", "VARCHAR(50) DEFAULT 'VIGENTE'"),
            ("supersedes_id", "INTEGER"),
            ("superseded_by_title", "VARCHAR(255)"),
            ("markdown_content", "TEXT"),
            ("original_pdf_url", "VARCHAR(500)")
        ]:
            try:
                conn.execute(text(f"ALTER TABLE document_items ADD COLUMN {col_name} {col_type}"))
                conn.commit()
            except Exception:
                pass

    # Ensure default system settings
    db = SessionLocal()
    try:
        defaults = [
            ("autonomous_mode", "false", "Modo agéntico autónomo para auto-indexar comunicados clasificados relevantes"),
            ("autonomous_threshold", "85", "Umbral mínimo de porcentaje de confianza para auto-indexar"),
            ("require_ud_domain", "true", "Guardrail: Exigir que el remitente sea @udistrital.edu.co para auto-indexar"),
            ("conflict_guardrail", "true", "Guardrail: Detener auto-indexación si se detectan cláusulas de derogación/conflicto")
        ]
        for key, val, desc in defaults:
            s = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if not s:
                db.add(SystemSetting(key=key, value=val, description=desc))
        db.commit()
    finally:
        db.close()


