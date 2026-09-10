from typing import Optional
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool
from app.core.config import settings
from app.db.models import Base, SystemSetting


def is_postgres_url(url: str) -> bool:
    """Checks whether the database URL targets a PostgreSQL database."""
    clean = (url or "").strip().lower()
    return clean.startswith("postgresql://") or clean.startswith("postgresql+") or clean.startswith("postgres://")


def normalize_db_url(url: str) -> str:
    """Normalizes legacy or driver-omitted postgres URLs."""
    if not url:
        return ""
    clean = url.strip()
    if clean.lower().startswith("postgres://"):
        return "postgresql://" + clean[11:]
    return clean


def create_db_engine(db_url: Optional[str] = None, **engine_kwargs) -> Engine:
    """
    Creates a production-ready SQLAlchemy Engine.
    - PostgreSQL: Configured with QueuePool for high concurrency (>200 users) with
      pool_size=30, max_overflow=50, pool_recycle=1800s, pool_pre_ping=True, pool_timeout=30s.
    - SQLite: Configured with check_same_thread=False, using StaticPool for in-memory databases.
    """
    raw_url = db_url if db_url is not None else settings.DATABASE_URL
    url = normalize_db_url(raw_url)

    if is_postgres_url(url):
        poolclass = engine_kwargs.pop("poolclass", QueuePool)
        pool_size = engine_kwargs.pop("pool_size", getattr(settings, "DB_POOL_SIZE", 30))
        max_overflow = engine_kwargs.pop("max_overflow", getattr(settings, "DB_MAX_OVERFLOW", 50))
        pool_recycle = engine_kwargs.pop("pool_recycle", getattr(settings, "DB_POOL_RECYCLE", 1800))
        pool_timeout = engine_kwargs.pop("pool_timeout", getattr(settings, "DB_POOL_TIMEOUT", 30))
        pool_pre_ping = engine_kwargs.pop("pool_pre_ping", getattr(settings, "DB_POOL_PRE_PING", True))

        return create_engine(
            url,
            poolclass=poolclass,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            pool_pre_ping=pool_pre_ping,
            pool_timeout=pool_timeout,
            **engine_kwargs
        )
    elif "sqlite" in url:
        connect_args = engine_kwargs.pop("connect_args", {})
        connect_args.setdefault("check_same_thread", False)

        is_in_memory = ":memory:" in url or url.rstrip("/") in ("sqlite:", "sqlite:/")
        if is_in_memory:
            poolclass = engine_kwargs.pop("poolclass", StaticPool)
            return create_engine(
                url,
                connect_args=connect_args,
                poolclass=poolclass,
                **engine_kwargs
            )
        return create_engine(
            url,
            connect_args=connect_args,
            **engine_kwargs
        )
    else:
        return create_engine(url, **engine_kwargs)


# Module-level engine and session factory
engine = create_db_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine: Optional[Engine] = None):
    """
    Dialect-agnostic database initialization.
    Tables are created via Base.metadata.create_all(bind=engine).
    Legacy SQLite schema migrations are applied conditionally only on SQLite.
    Default system settings are ensured.
    """
    curr_engine = target_engine or engine
    Base.metadata.create_all(bind=curr_engine)

    # Dialect-specific migrations ONLY for SQLite legacy databases
    if curr_engine.dialect.name == "sqlite":
        try:
            inspector = inspect(curr_engine)
            existing_tables = inspector.get_table_names()

            if "document_items" in existing_tables:
                existing_cols = {c["name"] for c in inspector.get_columns("document_items")}
                for col_name, col_type in [
                    ("validity_status", "VARCHAR(50) DEFAULT 'VIGENTE'"),
                    ("supersedes_id", "INTEGER"),
                    ("superseded_by_title", "VARCHAR(255)"),
                    ("markdown_content", "TEXT"),
                    ("scan_image_path", "VARCHAR(500)"),
                    ("original_pdf_url", "VARCHAR(500)")
                ]:
                    if col_name not in existing_cols:
                        try:
                            with curr_engine.connect() as conn:
                                conn.execute(text(f"ALTER TABLE document_items ADD COLUMN {col_name} {col_type}"))
                                conn.commit()
                        except Exception:
                            pass

            if "security_penalty_logs" in existing_tables:
                existing_cols = {c["name"] for c in inspector.get_columns("security_penalty_logs")}
                if "mac_address" not in existing_cols:
                    try:
                        with curr_engine.connect() as conn:
                            conn.execute(text("ALTER TABLE security_penalty_logs ADD COLUMN mac_address VARCHAR(64)"))
                            conn.commit()
                    except Exception:
                        pass
        except Exception:
            pass

    # Ensure default system settings
    SessionCls = sessionmaker(autocommit=False, autoflush=False, bind=curr_engine) if target_engine else SessionLocal
    db = SessionCls()
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
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
