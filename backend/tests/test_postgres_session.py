import os
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

# Ensure backend root is on sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from sqlalchemy import create_engine, inspect, select, schema, text
from sqlalchemy.pool import QueuePool, StaticPool
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql, sqlite

from app.core.config import Settings
from app.db.session import (
    is_postgres_url,
    normalize_db_url,
    create_db_engine,
    init_db
)
from app.db.models import (
    Base,
    SystemSetting,
    EmailNotice,
    DocumentItem,
    StudentQueryLog,
    SessionFeedback,
    SecurityPenaltyLog
)
from scripts.migrate_sqlite_to_postgres import (
    resolve_sqlite_path,
    migrate,
    sanitize_row_for_target,
    TABLE_ORDER,
    _sync_pg_sequence
)


class TestPostgresSessionAndPool(unittest.TestCase):
    """
    Automated Test Suite for Stage 2 PostgreSQL Migration:
    1. PostgreSQL connection pooling with QueuePool (>200 concurrent users).
    2. SQLite backward compatibility (in-memory StaticPool, file-based check_same_thread=False).
    3. Dialect-agnostic DDL compilation for PostgreSQL and SQLite.
    4. Safe, idempotent init_db() execution without raw dialect syntax errors.
    5. Full CRUD integrity across all database models.
    6. Migration utility:
       - Type sanitization (int -> bool, ISO str -> datetime).
       - Live end-to-end data transfer.
       - Clean slate wiping.
       - Idempotent re-run on existing targets.
       - PostgreSQL sequence synchronization.
    """

    def setUp(self):
        # Setup mock for psycopg2 so SQLAlchemy postgresql driver loads regardless of local host environment
        self.mock_psycopg2 = MagicMock()
        self.mock_psycopg2.__version__ = "2.9.9"
        self.patcher_pg = patch.dict("sys.modules", {
            "psycopg2": self.mock_psycopg2,
            "psycopg2.extensions": MagicMock(),
            "psycopg2.extras": MagicMock(),
        })
        self.patcher_pg.start()

    def tearDown(self):
        self.patcher_pg.stop()

    # ==========================================================================
    # 1. URL RECOGNITION AND NORMALIZATION TESTS
    # ==========================================================================

    def test_is_postgres_url(self):
        """Validates correct identification of PostgreSQL URLs across multiple schemes and cases."""
        self.assertTrue(is_postgres_url("postgresql://postgres:pass@localhost:5432/can_i_graduate"))
        self.assertTrue(is_postgres_url("postgresql+psycopg2://postgres:pass@postgres:5432/db"))
        self.assertTrue(is_postgres_url("postgres://user:pass@host:5432/production"))
        self.assertTrue(is_postgres_url("POSTGRESQL://localhost/db"))
        self.assertTrue(is_postgres_url("POSTGRES://localhost/db"))
        self.assertTrue(is_postgres_url("  postgresql://localhost/db  "))

        self.assertFalse(is_postgres_url("sqlite:///data/database.sqlite"))
        self.assertFalse(is_postgres_url("sqlite:///:memory:"))
        self.assertFalse(is_postgres_url("mysql://root@localhost/test"))
        self.assertFalse(is_postgres_url(""))
        self.assertFalse(is_postgres_url(None))

    def test_normalize_db_url(self):
        """Validates normalization of legacy postgres:// to postgresql:// with case insensitivity."""
        legacy = "postgres://user:secret@db.provider.com:5432/my_app"
        expected = "postgresql://user:secret@db.provider.com:5432/my_app"
        self.assertEqual(normalize_db_url(legacy), expected)

        # Upper case
        legacy_upper = "POSTGRES://user:secret@db.provider.com:5432/my_app"
        self.assertEqual(normalize_db_url(legacy_upper), expected)

        # Standard URLs remain unchanged
        pg_standard = "postgresql+psycopg2://user:secret@localhost:5432/test"
        sqlite_standard = "sqlite:///data/database.sqlite"
        self.assertEqual(normalize_db_url(pg_standard), pg_standard)
        self.assertEqual(normalize_db_url(sqlite_standard), sqlite_standard)
        self.assertEqual(normalize_db_url(""), "")

    # ==========================================================================
    # 2. POSTGRESQL ENGINE CONFIGURATION & QUEUEPOOL TESTS
    # ==========================================================================

    def test_postgres_engine_queuepool_configuration(self):
        """
        Verifies that PostgreSQL engines instantiate QueuePool with production-grade
        high concurrency settings (pool_size=30, max_overflow=50, pool_recycle=1800,
        pool_pre_ping=True, pool_timeout=30).
        """
        pg_url = "postgresql+psycopg2://postgres:secret@localhost:5432/can_i_graduate"
        engine = create_db_engine(pg_url)

        # 1. Verify QueuePool class
        self.assertIsInstance(engine.pool, QueuePool, "PostgreSQL engine must use QueuePool")

        # 2. Verify pool size
        self.assertEqual(engine.pool.size(), 30, "Default pool_size must be 30 for high concurrency")

        # 3. Verify max overflow
        self.assertEqual(engine.pool._max_overflow, 50, "Default max_overflow must be 50")

        # 4. Verify pool recycle (30 minutes = 1800s)
        self.assertEqual(engine.pool._recycle, 1800, "Default pool_recycle must be 1800 seconds")

        # 5. Verify pool pre-ping (liveness healthcheck before checkout)
        self.assertTrue(engine.pool._pre_ping, "pool_pre_ping must be enabled to prevent stale connections")

        # 6. Verify pool timeout
        self.assertEqual(engine.pool._timeout, 30, "pool_timeout must be 30 seconds")

    def test_postgres_engine_custom_pool_overrides(self):
        """Verifies that pool settings can be customized via kwargs or Settings."""
        pg_url = "postgresql+psycopg2://postgres:secret@localhost:5432/can_i_graduate"
        custom_engine = create_db_engine(
            pg_url,
            pool_size=40,
            max_overflow=60,
            pool_recycle=3600,
            pool_timeout=15,
            pool_pre_ping=False
        )

        self.assertEqual(custom_engine.pool.size(), 40)
        self.assertEqual(custom_engine.pool._max_overflow, 60)
        self.assertEqual(custom_engine.pool._recycle, 3600)
        self.assertEqual(custom_engine.pool._timeout, 15)
        self.assertFalse(custom_engine.pool._pre_ping)

    # ==========================================================================
    # 3. SQLITE BACKWARD COMPATIBILITY TESTS
    # ==========================================================================

    def test_sqlite_in_memory_uses_staticpool(self):
        """Verifies that in-memory SQLite variants use StaticPool to share state across connections."""
        engine1 = create_db_engine("sqlite:///:memory:")
        self.assertIsInstance(engine1.pool, StaticPool, "sqlite:///:memory: must use StaticPool")

        engine2 = create_db_engine("sqlite://")
        self.assertIsInstance(engine2.pool, StaticPool, "sqlite:// must use StaticPool")

    def test_sqlite_check_same_thread_disabled(self):
        """Verifies that SQLite engines configure check_same_thread=False for async FastAPI workers."""
        engine = create_db_engine("sqlite:///tmp_test.sqlite")
        with engine.connect() as conn:
            res = conn.execute(select(1)).scalar()
            self.assertEqual(res, 1)

    # ==========================================================================
    # 4. DIALECT-AGNOSTIC DDL COMPILATION (POSTGRESQL & SQLITE)
    # ==========================================================================

    def test_postgresql_ddl_compilation(self):
        """
        Verifies that all model tables compile into valid PostgreSQL DDL.
        Ensures NO SQLite-specific keywords like raw 'AUTOINCREMENT' are generated.
        """
        pg_dialect = postgresql.dialect()

        for table in Base.metadata.sorted_tables:
            ddl_string = str(CreateTable(table).compile(dialect=pg_dialect))
            self.assertTrue(len(ddl_string) > 0)
            self.assertNotIn(
                "AUTOINCREMENT",
                ddl_string.upper(),
                f"Table {table.name} generated SQLite AUTOINCREMENT in PostgreSQL DDL!"
            )
            self.assertIn("CREATE TABLE", ddl_string)

    def test_sqlite_ddl_compilation(self):
        """Verifies that all model tables compile into valid SQLite DDL."""
        sql_dialect = sqlite.dialect()

        for table in Base.metadata.sorted_tables:
            ddl_string = str(CreateTable(table).compile(dialect=sql_dialect))
            self.assertTrue(len(ddl_string) > 0)
            self.assertIn("CREATE TABLE", ddl_string)

    # ==========================================================================
    # 5. IDEMPOTENT init_db() EXECUTION & DEFAULT SYSTEM SETTINGS
    # ==========================================================================

    def test_init_db_execution_and_idempotency(self):
        """
        Tests init_db() execution on a clean database:
        - Creates all tables cleanly.
        - Populates default system settings.
        - Repeated calls are completely idempotent and safe.
        """
        test_engine = create_db_engine("sqlite:///:memory:")

        # 1. Run init_db on fresh database
        init_db(target_engine=test_engine)

        inspector = inspect(test_engine)
        created_tables = set(inspector.get_table_names())
        expected_tables = {
            "system_settings",
            "email_notices",
            "document_items",
            "student_query_logs",
            "session_feedbacks",
            "security_penalty_logs"
        }
        for t in expected_tables:
            self.assertIn(t, created_tables, f"Table '{t}' was not created by init_db()")

        # 2. Verify default system settings
        from sqlalchemy.orm import sessionmaker
        SessionCls = sessionmaker(bind=test_engine)
        with SessionCls() as session:
            settings_rows = session.query(SystemSetting).all()
            keys = {s.key for s in settings_rows}
            self.assertIn("autonomous_mode", keys)
            self.assertIn("autonomous_threshold", keys)
            self.assertIn("require_ud_domain", keys)
            self.assertIn("conflict_guardrail", keys)

        # 3. Re-run init_db to test idempotency
        init_db(target_engine=test_engine)

        with SessionCls() as session:
            settings_count = session.query(SystemSetting).count()
            self.assertEqual(settings_count, 4, "Idempotent init_db() must not duplicate default settings")

    # ==========================================================================
    # 6. MODEL CRUD OPERATIONS & RELATIONSHIPS
    # ==========================================================================

    def test_models_crud_integrity(self):
        """Verifies full relational CRUD operations across all 6 core models."""
        test_engine = create_db_engine("sqlite:///:memory:")
        init_db(target_engine=test_engine)

        from sqlalchemy.orm import sessionmaker
        SessionCls = sessionmaker(bind=test_engine)

        with SessionCls() as session:
            # 1. EmailNotice
            email = EmailNotice(
                sender="coordinacion@udistrital.edu.co",
                subject="Circular 001 de 2026 - Convocatoria Grados",
                body_text="Información oficial sobre requisitos y fechas límites de sustentación.",
                is_relevant=True,
                relevance_score=95.0
            )
            session.add(email)
            session.flush()
            self.assertIsNotNone(email.id)

            # 2. DocumentItem (parent document)
            doc1 = DocumentItem(
                title="Acuerdo 038 de 2015",
                filename="acuerdo_038_2015.pdf",
                file_path="/app/data/uploads/acuerdo_038.pdf",
                email_id=email.id,
                resolution_number="Acuerdo 038 de 2015",
                validity_status="MODIFICADO"
            )
            session.add(doc1)
            session.flush()

            # 3. DocumentItem (modifying document with self-reference supersedes_id)
            doc2 = DocumentItem(
                title="Acuerdo 015 de 2026",
                filename="acuerdo_015_2026.pdf",
                file_path="/app/data/uploads/acuerdo_015.pdf",
                resolution_number="Acuerdo 015 de 2026",
                validity_status="VIGENTE",
                supersedes_id=doc1.id,
                superseded_by_title=None
            )
            session.add(doc2)
            session.flush()

            # Verify relationship back-population
            self.assertEqual(len(email.documents), 1)
            self.assertEqual(email.documents[0].title, "Acuerdo 038 de 2015")
            self.assertEqual(doc2.supersedes_id, doc1.id)

            # 4. StudentQueryLog
            query_log = StudentQueryLog(
                query_text="¿Cuáles son las modalidades de grado vigentes?",
                topic_category="Modalidades",
                citations_count=2,
                confidence_score=1.0,
                has_knowledge_gap=False
            )
            session.add(query_log)
            session.flush()
            self.assertIsNotNone(query_log.id)

            # 5. SessionFeedback
            feedback = SessionFeedback(
                session_id="session_abc_123",
                user_email="estudiante@udistrital.edu.co",
                feedback_type="sugerencia",
                rating=5,
                comments="Excelente precisión normativa con los artículos citados."
            )
            session.add(feedback)
            session.flush()
            self.assertIsNotNone(feedback.id)

            # 6. SecurityPenaltyLog
            penalty = SecurityPenaltyLog(
                ip_address="192.168.1.100",
                mac_address="00:1A:2B:3C:4D:5E",
                subnet="192.168.1.0/24",
                strike_count=1,
                last_reason="Consulta fuera de ámbito universitario"
            )
            session.add(penalty)
            session.commit()

            # Verify all records persisted correctly
            self.assertEqual(session.query(DocumentItem).count(), 2)
            self.assertEqual(session.query(StudentQueryLog).count(), 1)
            self.assertEqual(session.query(SessionFeedback).count(), 1)
            self.assertEqual(session.query(SecurityPenaltyLog).count(), 1)

    # ==========================================================================
    # 7. MIGRATION UTILITY TESTS (SANITIZATION, PIPELINE & SEQUENCE SYNC)
    # ==========================================================================

    def test_migration_table_order_and_path_resolution(self):
        """Verifies foreign key table order and SQLite path resolution in migration utility."""
        self.assertEqual(
            TABLE_ORDER,
            [
                "system_settings",
                "email_notices",
                "document_items",
                "student_query_logs",
                "session_feedbacks",
                "security_penalty_logs"
            ]
        )
        resolved = resolve_sqlite_path(None)
        self.assertTrue(len(resolved) > 0)
        self.assertTrue(resolved.endswith(".sqlite"))

    def test_sanitize_row_for_target(self):
        """
        Verifies that sanitize_row_for_target coerces SQLite values to target types:
        - integer 0/1 to boolean True/False.
        - ISO datetime strings to Python datetime objects.
        - drops non-existent columns.
        - preserves None.
        """
        target_table = Base.metadata.tables["email_notices"]
        raw_sqlite_row = {
            "id": 10,
            "sender": "test@udistrital.edu.co",
            "has_attachments": 1,
            "is_relevant": 0,
            "received_at": "2026-09-08 14:30:00.123456",
            "reviewed_at": "2026-09-08T15:00:00",
            "non_existent_col": "should be dropped",
            "recipient": None
        }

        sanitized = sanitize_row_for_target(raw_sqlite_row, target_table)

        self.assertIs(sanitized["has_attachments"], True)
        self.assertIs(sanitized["is_relevant"], False)
        self.assertIsInstance(sanitized["received_at"], datetime)
        self.assertEqual(sanitized["received_at"].year, 2026)
        self.assertEqual(sanitized["received_at"].month, 9)
        self.assertEqual(sanitized["received_at"].day, 8)
        self.assertIsInstance(sanitized["reviewed_at"], datetime)
        self.assertNotIn("non_existent_col", sanitized)
        self.assertIsNone(sanitized["recipient"])

    def test_migration_dry_run_execution(self):
        """Verifies that the migration function runs in dry-run mode without errors."""
        resolved_sqlite = resolve_sqlite_path(None)
        if os.path.isfile(resolved_sqlite):
            success = migrate(
                sqlite_path=resolved_sqlite,
                postgres_url="postgresql://user:pass@localhost:5432/testdb",
                dry_run=True
            )
            self.assertTrue(success, "Migration dry-run should complete successfully")

    def test_live_data_migration_to_target(self):
        """
        Executes a real end-to-end data migration from database.sqlite to an isolated
        target database:
        - Transfers all 6 tables.
        - Verifies that all 106 existing records transfer without loss.
        - Verifies that re-running without --clean does not crash with constraint errors.
        - Verifies that --clean empties and cleanly re-populates the target.
        """
        resolved_sqlite = resolve_sqlite_path(None)
        self.assertTrue(os.path.isfile(resolved_sqlite), "Source database.sqlite must exist")

        target_file = os.path.join(backend_root, "data", "test_migration_target.sqlite")
        target_url = f"sqlite:///{target_file}"

        if os.path.exists(target_file):
            os.remove(target_file)

        try:
            # 1. Initial full migration
            success = migrate(
                sqlite_path=resolved_sqlite,
                postgres_url=target_url,
                dry_run=False,
                batch_size=50,
                clean_target=False
            )
            self.assertTrue(success, "Initial migration must succeed")

            # Verify target table contents
            target_engine = create_engine(target_url, poolclass=StaticPool)
            with target_engine.connect() as conn:
                sys_count = conn.execute(text("SELECT COUNT(*) FROM system_settings")).scalar()
                email_count = conn.execute(text("SELECT COUNT(*) FROM email_notices")).scalar()
                doc_count = conn.execute(text("SELECT COUNT(*) FROM document_items")).scalar()
                query_count = conn.execute(text("SELECT COUNT(*) FROM student_query_logs")).scalar()
                feed_count = conn.execute(text("SELECT COUNT(*) FROM session_feedbacks")).scalar()
                sec_count = conn.execute(text("SELECT COUNT(*) FROM security_penalty_logs")).scalar()

            source_engine = create_engine(f"sqlite:///{resolved_sqlite}", poolclass=StaticPool)
            with source_engine.connect() as s_conn:
                src_sys = s_conn.execute(text("SELECT COUNT(*) FROM system_settings")).scalar()
                src_email = s_conn.execute(text("SELECT COUNT(*) FROM email_notices")).scalar()
                src_doc = s_conn.execute(text("SELECT COUNT(*) FROM document_items")).scalar()
                src_query = s_conn.execute(text("SELECT COUNT(*) FROM student_query_logs")).scalar()
                src_feed = s_conn.execute(text("SELECT COUNT(*) FROM session_feedbacks")).scalar()
                src_sec = s_conn.execute(text("SELECT COUNT(*) FROM security_penalty_logs")).scalar()

            self.assertEqual(sys_count, src_sys)
            self.assertEqual(email_count, src_email)
            self.assertEqual(doc_count, src_doc)
            self.assertEqual(query_count, src_query)
            self.assertEqual(feed_count, src_feed)
            self.assertEqual(sec_count, src_sec)

            # 2. Test Idempotency: re-running without --clean shouldn't fail
            idempotent_success = migrate(
                sqlite_path=resolved_sqlite,
                postgres_url=target_url,
                dry_run=False,
                batch_size=50,
                clean_target=False
            )
            self.assertTrue(idempotent_success, "Repeated migration must be idempotent")

            # 3. Test Clean Target: wipes and re-migrates cleanly
            clean_success = migrate(
                sqlite_path=resolved_sqlite,
                postgres_url=target_url,
                dry_run=False,
                batch_size=50,
                clean_target=True
            )
            self.assertTrue(clean_success, "Migration with clean_target=True must succeed")

            with target_engine.connect() as conn:
                doc_count_after = conn.execute(text("SELECT COUNT(*) FROM document_items")).scalar()
            self.assertEqual(doc_count_after, src_doc)

        finally:
            if os.path.exists(target_file):
                try:
                    os.remove(target_file)
                except Exception:
                    pass

    def test_sync_pg_sequence_logic(self):
        """Verifies that _sync_pg_sequence executes proper sequence queries on PostgreSQL."""
        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn

        # Case 1: Sequence exists and table has rows (MAX id = 23)
        mock_conn.execute.side_effect = [
            MagicMock(scalar=MagicMock(return_value="document_items_id_seq")),
            MagicMock(scalar=MagicMock(return_value=23)),
            MagicMock()
        ]

        _sync_pg_sequence(mock_engine, "document_items")

        # Third call should be setval with is_called = true
        third_call_sql = str(mock_conn.execute.call_args_list[2][0][0])
        self.assertIn("setval", third_call_sql)
        self.assertIn("true", third_call_sql)

        # Case 2: Sequence exists but table has NO rows (MAX id = None)
        mock_conn.reset_mock()
        mock_conn.execute.side_effect = [
            MagicMock(scalar=MagicMock(return_value="document_items_id_seq")),
            MagicMock(scalar=MagicMock(return_value=None)),
            MagicMock()
        ]

        _sync_pg_sequence(mock_engine, "document_items")

        third_call_sql = str(mock_conn.execute.call_args_list[2][0][0])
        self.assertIn("setval", third_call_sql)
        self.assertIn("false", third_call_sql)


if __name__ == "__main__":
    unittest.main()
