"""
Integrity and Repository Hygiene Test Suite.

Verifies the constraints outlined in ORIGINAL_REQUEST.md and PROJECT.md:
1. Compact AI agent guides: backend/AGENTS.md and frontend/AGENTS.md strictly under 200 lines.
2. Modular documentation: architecture and convention docs exist with substantive content (> 50 lines).
3. Residual database cleanup: no tmp_test.sqlite artifacts left in root or backend/.
4. Orphan component deletion: legacy/duplicate frontend components have been removed.
"""

from pathlib import Path
import pytest

# Base project root resolved relative to this test file location:
# backend/tests/test_agent_docs_integrity.py -> root is 3 levels up
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_agents_md_line_counts_strictly_under_200():
    """Verify backend/AGENTS.md and frontend/AGENTS.md exist and their line count is strictly < 200 lines."""
    agent_docs = [
        PROJECT_ROOT / "backend" / "AGENTS.md",
        PROJECT_ROOT / "frontend" / "AGENTS.md",
    ]

    for doc_path in agent_docs:
        assert doc_path.is_file(), f"Agent doc not found at {doc_path}"
        lines = doc_path.read_text(encoding="utf-8").splitlines()
        line_count = len(lines)
        assert line_count > 0, f"{doc_path} is empty"
        assert (
            line_count < 200
        ), f"{doc_path} exceeds 200 lines (actual count: {line_count} lines)"


def test_modular_documentation_exists():
    """Verify modular documentation files exist and have substantive content (> 50 lines)."""
    modular_docs = [
        PROJECT_ROOT / "backend" / "docs" / "architecture.md",
        PROJECT_ROOT / "backend" / "docs" / "database_and_caching.md",
        PROJECT_ROOT / "frontend" / "docs" / "architecture_and_state.md",
        PROJECT_ROOT / "frontend" / "docs" / "components_and_styling.md",
    ]

    for doc_path in modular_docs:
        assert doc_path.is_file(), f"Modular documentation missing: {doc_path}"
        lines = doc_path.read_text(encoding="utf-8").splitlines()
        line_count = len(lines)
        assert (
            line_count > 50
        ), f"{doc_path} lacks substantive content (only {line_count} lines; expected > 50)"


def test_residual_sqlite_artifacts_cleaned():
    """Verify tmp_test.sqlite and backend/tmp_test.sqlite do not exist."""
    sqlite_artifacts = [
        PROJECT_ROOT / "tmp_test.sqlite",
        PROJECT_ROOT / "backend" / "tmp_test.sqlite",
    ]

    for artifact in sqlite_artifacts:
        assert not artifact.exists(), f"Residual SQLite test artifact found at {artifact}"


def test_orphan_frontend_components_deleted():
    """Verify orphan and legacy frontend components do not exist in frontend/src/components/."""
    orphan_components = [
        PROJECT_ROOT / "frontend" / "src" / "components" / "AdminNavbar.tsx",
        PROJECT_ROOT / "frontend" / "src" / "components" / "StatusToggle.tsx",
        PROJECT_ROOT / "frontend" / "src" / "components" / "TriageCard.tsx",
        PROJECT_ROOT / "frontend" / "src" / "components" / "SmoothMarkdown.tsx",
        PROJECT_ROOT / "frontend" / "src" / "components" / "UniqueLoading.tsx",
        PROJECT_ROOT / "frontend" / "src" / "components" / "ui" / "unique-loading.tsx",
    ]

    for component in orphan_components:
        assert not component.exists(), f"Orphan frontend component still exists: {component}"

