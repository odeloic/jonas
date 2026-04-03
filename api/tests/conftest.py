import sys
from pathlib import Path

import pytest

# Make api/ importable when running pytest from the api/ directory or project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

from config import settings  # noqa: E402
from services.llm_service import LLMService  # noqa: E402


@pytest.fixture(scope="session")
def llm_service() -> LLMService:
    """Single LLMService instance shared across the test session."""
    return LLMService()


@pytest.fixture(scope="session")
def langfuse_client():
    """Langfuse client for reading traces back in eval tests.

    Returns None if tracing is disabled or keys are not configured.
    """
    if not settings.langfuse_enabled:
        return None
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    from langfuse import Langfuse  # noqa: PLC0415

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


@pytest.fixture
def no_langfuse(monkeypatch):
    """Disable Langfuse for a single test — no network calls to the tracing server."""
    monkeypatch.setattr(settings, "langfuse_enabled", False)
