#!/usr/bin/env python3
"""
CanIGraduateUD-RAG - SQLite to PostgreSQL Data Migration Utility
Transfers all existing application data from SQLite to PostgreSQL with:
- Automatic schema creation via SQLAlchemy models.
- Foreign-key safe insertion order and conflict handling.
- Strict data type sanitization (converting SQLite int booleans to Python bool,
  and ISO string timestamps to real datetime objects).
- PostgreSQL sequence synchronization for auto-increment PKs.
- Detailed progress reporting, dry-run simulation, and clean-slate wiping.
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine, text, inspect, MetaData, Table, select
from sqlalchemy.types import Boolean, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects import postgresql, sqlite

from app.db.models import Base
from app.db.session import create_db_engine, is_postgres_url, normalize_db_url
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("sqlite_to_postgres_migration")

# Explicit table migration order to respect foreign key hierarchies
TABLE_ORDER = [
    "system_settings",
    "email_notices",
    "document_items",
    "student_query_logs",
    "session_feedbacks",
    "security_penalty_logs"
]


def resolve_sqlite_path(arg_path: Optional[str]) -> str:
    """Finds the source SQLite database file."""
    if arg_path and os.path.isfile(arg_path):
        return os.path.abspath(arg_path)

    # Check settings.DATABASE_URL
    if settings.DATABASE_URL and "sqlite" in settings.DATABASE_URL:
        clean = settings.DATABASE_URL.replace("sqlite:////", "/").replace("sqlite:///", "/")
        if os.path.isfile(clean):
            return os.path.abspath(clean)

    # Check standard project candidates
    candidates = [
        os.path.join(backend_dir, "data", "database.sqlite"),
        os.path.join(settings.DATA_DIR, "database.sqlite"),
        os.path.join(os.path.dirname(backend_dir), "data", "database.sqlite")
    ]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)

    return arg_path or candidates[0]


def sanitize_row_for_target(row_dict: Dict[str, Any], target_table: Table) -> Dict[str, Any]:
    """
    Sanitizes and type-coerces raw SQLite values so they comply with strictly-typed
    PostgreSQL column definitions:
    1. Converts integer 0/1 or string "true"/"false" into native Python booleans for Boolean columns.
    2. Parses ISO strings into native Python datetime objects for DateTime columns.
    3. Filters out any extraneous fields not defined on the target table.
    """
    sanitized: Dict[str, Any] = {}
    for col_name, val in row_dict.items():
        if col_name not in target_table.c:
            continue

        col = target_table.c[col_name]
        col_type = col.type

        if val is None:
            sanitized[col_name] = None
        elif isinstance(col_type, Boolean):
            if isinstance(val, bool):
                sanitized[col_name] = val
            elif isinstance(val, (int, float)):
                sanitized[col_name] = bool(val)
            elif isinstance(val, str):
                sanitized[col_name] = val.strip().lower() in ("true", "1", "t", "yes", "y")
            else:
                sanitized[col_name] = bool(val)
        elif isinstance(col_type, DateTime):
            if isinstance(val, datetime):
                sanitized[col_name] = val
            elif isinstance(val, str):
                clean_str = val.strip().replace("T", " ")
                dt_obj = None
                for fmt in (
                    "%Y-%m-%d %H:%M:%S.%f",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d",
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%S"
                ):
                    try:
                        dt_obj = datetime.strptime(clean_str, fmt)
                        break
                    except ValueError:
                        continue
                if dt_obj is None:
                    try:
                        dt_obj = datetime.fromisoformat(val)
                    except Exception:
                        dt_obj = None
                sanitized[col_name] = dt_obj
            else:
                sanitized[col_name] = val
        else:
            sanitized[col_name] = val

    return sanitized


def clean_target_tables(engine, ordered_tables: List[str]) -> bool:
    """
    Safely empties target tables in reverse dependency order.
    Uses separate transactions to prevent PostgreSQL InFailedSqlTransaction cascade errors.
    """
    is_pg = engine.dialect.name == "postgresql"

    # Attempt PostgreSQL batch truncate first
    if is_pg:
        try:
            with engine.begin() as conn:
                tbl_names = ", ".join(f'"{t}"' for t in reversed(ordered_tables))
                conn.execute(text(f"TRUNCATE TABLE {tbl_names} CASCADE"))
                logger.info(f"  Truncadas tablas masivamente en PostgreSQL: {tbl_names}")
                return True
        except Exception as batch_err:
            logger.warning(f"  Truncate masivo no disponible ({batch_err}), truncando individualmente...")

    # Fallback to table-by-table clean with individual transactions
    for t_name in reversed(ordered_tables):
        cleaned = False
        if is_pg:
            try:
                with engine.begin() as conn:
                    conn.execute(text(f'TRUNCATE TABLE "{t_name}" CASCADE'))
                    logger.info(f"  Truncada tabla: {t_name}")
                    cleaned = True
            except Exception as tr_err:
                logger.debug(f"  TRUNCATE falló para {t_name}: {tr_err}, intentando DELETE...")

        if not cleaned:
            try:
                with engine.begin() as conn:
                    conn.execute(text(f'DELETE FROM "{t_name}"'))
                    logger.info(f"  Limpiada tabla con DELETE: {t_name}")
            except Exception as del_err:
                logger.warning(f"  No se pudo limpiar tabla {t_name}: {del_err}")
                return False
    return True


def migrate(
    sqlite_path: str,
    postgres_url: str,
    dry_run: bool = False,
    batch_size: int = 500,
    clean_target: bool = False
) -> bool:
    """
    Executes the migration process from SQLite to PostgreSQL.
    """
    logger.info("=" * 70)
    logger.info("CAN I GRADUATE UD - MIGRACIÓN SQLITE A POSTGRESQL")
    logger.info("=" * 70)
    logger.info(f"📁 Origen SQLite:      {sqlite_path}")
    logger.info(f"🐘 Destino:            {postgres_url.split('@')[-1] if '@' in postgres_url else postgres_url}")
    logger.info(f"🔍 Modo Dry-Run:       {'ACTIVADO (no se escribirán datos)' if dry_run else 'DESACTIVADO'}")
    logger.info(f"📦 Tamaño de Batch:    {batch_size}")
    logger.info(f"🧹 Limpiar Destino:    {clean_target}")
    logger.info("-" * 70)

    if not os.path.isfile(sqlite_path):
        logger.error(f"❌ El archivo SQLite no existe en: {sqlite_path}")
        return False

    # 1. Connect to SQLite
    sqlite_engine = create_engine(
        f"sqlite:///{sqlite_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    sqlite_inspector = inspect(sqlite_engine)
    available_sqlite_tables = set(sqlite_inspector.get_table_names())
    logger.info(f"Tablas encontradas en SQLite: {sorted(list(available_sqlite_tables))}")

    # Build final migration order (defined order first, then any extra tables)
    ordered_tables = [t for t in TABLE_ORDER if t in available_sqlite_tables]
    for t in sorted(available_sqlite_tables):
        if t not in ordered_tables and not t.startswith("sqlite_"):
            ordered_tables.append(t)

    logger.info(f"Secuencia de migración planificada: {' -> '.join(ordered_tables)}")

    # 2. Count rows in SQLite
    total_source_rows: Dict[str, int] = {}
    with sqlite_engine.connect() as s_conn:
        for t_name in ordered_tables:
            count = s_conn.execute(text(f"SELECT COUNT(*) FROM {t_name}")).scalar() or 0
            total_source_rows[t_name] = count
            logger.info(f"  • {t_name}: {count} filas")

    if dry_run:
        logger.info("-" * 70)
        logger.info("✅ Simulación Dry-Run completada satisfactoriamente. No se realizaron cambios.")
        return True

    # 3. Connect to Target Engine
    target_norm_url = normalize_db_url(postgres_url)
    try:
        target_engine = create_db_engine(target_norm_url)
        with target_engine.connect() as test_conn:
            test_conn.execute(text("SELECT 1"))
        logger.info("✅ Conexión con destino establecida exitosamente.")
    except Exception as e:
        logger.error(f"❌ Error al conectar con base de datos destino: {e}")
        return False

    is_pg = target_engine.dialect.name == "postgresql"

    # 4. Create Tables in Target Database
    logger.info("🔨 Creando/verificando esquemas y tablas en destino...")
    Base.metadata.create_all(bind=target_engine)
    logger.info("✅ Esquemas de tablas sincronizados.")

    # 5. Clean target if requested
    if clean_target:
        logger.warning("⚠️  Limpiando tablas existentes en base de datos destino...")
        clean_target_tables(target_engine, ordered_tables)

    # 6. Transfer Data Table by Table
    migration_summary: Dict[str, Dict[str, Any]] = {}

    target_meta = MetaData()
    target_meta.reflect(bind=target_engine)

    # In PostgreSQL, attempt to disable triggers/FK checks during bulk migration if superuser
    if is_pg:
        try:
            with target_engine.begin() as rep_conn:
                rep_conn.execute(text("SET session_replication_role = 'replica'"))
        except Exception:
            pass

    try:
        for t_name in ordered_tables:
            row_count = total_source_rows[t_name]
            logger.info(f"\n🚀 Migrando tabla: {t_name} ({row_count} filas)...")
            if row_count == 0:
                logger.info(f"  Tabla {t_name} vacía en SQLite. Omitiendo transferencia de registros.")
                migration_summary[t_name] = {"source": 0, "target": 0, "status": "OK (Vacía)"}
                continue

            if t_name not in target_meta.tables:
                logger.warning(f"⚠️  Tabla {t_name} no existe en metadatos de destino. Omitiendo.")
                migration_summary[t_name] = {"source": row_count, "target": 0, "status": "SKIPPED"}
                continue

            target_table = target_meta.tables[t_name]

            # Read typed rows from SQLite using SQLAlchemy model table if available
            with sqlite_engine.connect() as s_conn:
                if t_name in Base.metadata.tables:
                    s_table = Base.metadata.tables[t_name]
                    # Order by ID if present to ensure parent records precede children
                    order_col = s_table.c.id if "id" in s_table.c else None
                    stmt = select(s_table)
                    if order_col is not None:
                        stmt = stmt.order_by(order_col.asc())
                    result = s_conn.execute(stmt)
                    rows = [dict(r._mapping) for r in result.fetchall()]
                else:
                    raw_result = s_conn.execute(text(f"SELECT * FROM {t_name} ORDER BY rowid ASC"))
                    cols = list(raw_result.keys())
                    rows = [dict(zip(cols, r)) for r in raw_result.fetchall()]

            # Insert into Target in batches with type sanitization and conflict avoidance
            inserted_count = 0
            with target_engine.begin() as conn:
                batch = []
                for row_dict in rows:
                    clean_dict = sanitize_row_for_target(row_dict, target_table)
                    batch.append(clean_dict)

                    if len(batch) >= batch_size:
                        _insert_batch(conn, target_table, batch, is_pg)
                        inserted_count += len(batch)
                        batch = []

                if batch:
                    _insert_batch(conn, target_table, batch, is_pg)
                    inserted_count += len(batch)

            # 7. Synchronize PostgreSQL sequence if id column exists
            if is_pg and "id" in target_table.c:
                _sync_pg_sequence(target_engine, t_name)

            # Verify count in target
            with target_engine.connect() as v_conn:
                target_count = v_conn.execute(text(f'SELECT COUNT(*) FROM "{t_name}"')).scalar() or 0

            status = "OK" if target_count >= row_count else "MISMATCH"
            migration_summary[t_name] = {"source": row_count, "target": target_count, "status": status}
            logger.info(f"  ✅ Tabla {t_name} migrada: SQLite={row_count} -> Destino={target_count} [{status}]")

    finally:
        # Restore normal replication role in PostgreSQL
        if is_pg:
            try:
                with target_engine.begin() as rep_conn:
                    rep_conn.execute(text("SET session_replication_role = 'origin'"))
            except Exception:
                pass

    # 8. Final Report
    logger.info("\n" + "=" * 70)
    logger.info("RESUMEN DE MIGRACIÓN SQLITE -> POSTGRESQL")
    logger.info("=" * 70)
    all_success = True
    for t_name, info in migration_summary.items():
        st = info["status"]
        if "MISMATCH" in st or "SKIPPED" in st:
            all_success = False
        logger.info(f"{t_name:<30} | Origen: {info['source']:<6} | Destino: {info['target']:<6} | {st}")

    logger.info("=" * 70)
    if all_success:
        logger.info("🎉 ¡MIGRACIÓN COMPLETADA EXITOSAMENTE SIN PÉRDIDA DE DATOS!")
    else:
        logger.warning("⚠️  La migración terminó con advertencias o discrepancias. Revisa los logs.")
    return all_success


def _insert_batch(conn, target_table: Table, batch: List[Dict[str, Any]], is_pg: bool):
    """Executes a bulk insert with conflict handling across dialects."""
    if not batch:
        return

    pk_cols = [c.name for c in target_table.primary_key.columns]

    if is_pg and pk_cols:
        # Handle conflicts gracefully in PostgreSQL
        insert_stmt = postgresql.insert(target_table)
        if target_table.name == "system_settings" and "key" in pk_cols:
            stmt = insert_stmt.on_conflict_do_update(
                index_elements=["key"],
                set_={c.name: c for c in insert_stmt.excluded if c.name != "key"}
            )
        else:
            stmt = insert_stmt.on_conflict_do_nothing(index_elements=pk_cols)
        conn.execute(stmt, batch)
        return

    if conn.dialect.name == "sqlite" and pk_cols:
        # Handle conflicts gracefully in SQLite
        insert_stmt = sqlite.insert(target_table)
        if target_table.name == "system_settings" and "key" in pk_cols:
            stmt = insert_stmt.on_conflict_do_update(
                index_elements=["key"],
                set_={c.name: c for c in insert_stmt.excluded if c.name != "key"}
            )
        else:
            stmt = insert_stmt.on_conflict_do_nothing(index_elements=pk_cols)
        conn.execute(stmt, batch)
        return

    # Fallback / standard insert
    conn.execute(target_table.insert(), batch)


def _sync_pg_sequence(engine, table_name: str):
    """
    Synchronizes the auto-increment sequence in PostgreSQL so subsequent INSERTs
    do not collide with existing primary key values.
    """
    try:
        with engine.begin() as conn:
            # Check sequence name
            seq_query = text(f"SELECT pg_get_serial_sequence('{table_name}', 'id')")
            seq_name = conn.execute(seq_query).scalar()
            if seq_name:
                max_id_query = text(f'SELECT MAX(id) FROM "{table_name}"')
                max_id = conn.execute(max_id_query).scalar()
                if max_id is not None:
                    conn.execute(text(f"SELECT setval('{seq_name}', {max_id}, true)"))
                    logger.info(f"  🔄 Secuencia '{seq_name}' sincronizada a {max_id}.")
                else:
                    conn.execute(text(f"SELECT setval('{seq_name}', 1, false)"))
    except Exception as seq_err:
        logger.debug(f"  Secuencia no sincronizada en '{table_name}': {seq_err}")


def main():
    parser = argparse.ArgumentParser(
        description="Migra los datos de SQLite a PostgreSQL para CanIGraduateUD-RAG."
    )
    parser.add_argument(
        "--sqlite-path",
        type=str,
        default=None,
        help="Ruta al archivo database.sqlite origen (opcional, se auto-detecta)."
    )
    parser.add_argument(
        "--postgres-url",
        type=str,
        default=None,
        help="URL de conexión a PostgreSQL (opcional, usa settings.DATABASE_URL si es postgres)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la migración mostrando el recuento de filas sin modificar PostgreSQL."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Cantidad de registros por inserción masiva (default: 500)."
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Limpia/trunca las tablas en destino antes de insertar."
    )

    args = parser.parse_args()

    sqlite_path = resolve_sqlite_path(args.sqlite_path)
    postgres_url = args.postgres_url or (settings.DATABASE_URL if is_postgres_url(settings.DATABASE_URL) else "")

    if not postgres_url and not args.dry_run:
        logger.error(
            "❌ Debes proporcionar una URL de PostgreSQL mediante --postgres-url o en "
            "la variable de entorno DATABASE_URL (ejemplo: postgresql+psycopg2://postgres:pass@localhost:5432/can_i_graduate)"
        )
        sys.exit(1)

    success = migrate(
        sqlite_path=sqlite_path,
        postgres_url=postgres_url or "postgresql://dummy:dummy@localhost:5432/dummy",
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        clean_target=args.clean
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
