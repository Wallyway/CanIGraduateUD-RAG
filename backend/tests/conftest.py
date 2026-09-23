import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def disable_external_jev_for_tests(monkeypatch):
    """Keep endpoint tests deterministic; Jev has dedicated mocked tests."""
    monkeypatch.setattr(settings, "JEV_ENABLED", False)
