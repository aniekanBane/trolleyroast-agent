from collections.abc import Iterator
from pathlib import Path

import pytest

from trolleyroast_agent.core.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    """Automatically clear settings cache before every test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def tmp_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Clear relevant env vars before each test so .env doesn't leak."""
    keys = [
        "DEBUG",
        "SUPABASE__PROJECT_URL",
        "SUPABASE__API_KEY",
        "SUPABASE__INGEST_PATH",
        "SUPABASE__AGENT_KEY",
        "FASTCRW__ENDPOINT_URL",
        "FASTCRW__API_KEY",
        "SCRAPER__TROLLEY_UK_SEARCH_URL",
        "EMAIL__PROVIDER",
        "EMAIL__DEFAULT_SENDER",
        "EMAIL__RESEND__API_KEY",
        "EMAIL__SMTP__HOST",
        "EMAIL__SMTP__PORT",
        "EMAIL__SMTP__REQUIRE_TLS",
        "LOGGING__FILE_DIRECTORY",
        "STATE_FILE_PATH",
    ]
    for k in keys:
        monkeypatch.delenv(k, raising=False)
    yield


@pytest.fixture
def valid_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Populate a minimal valid environment."""
    log_dir = tmp_path / "trolleyroast-logs"
    state_file = tmp_path / "trolleyroast_state.json"

    monkeypatch.setenv("LOGGING__FILE_DIRECTORY", str(log_dir))
    monkeypatch.setenv("STATE_FILE_PATH", str(state_file))

    monkeypatch.setenv("SUPABASE__PROJECT_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE__INGEST_PATH", "/functions/v1/agent-ingest")

    monkeypatch.setenv("FASTCRW__ENDPOINT_URL", "https://127.0.0.1:3000")

    monkeypatch.setenv("EMAIL__PROVIDER", "resend")
    monkeypatch.setenv("EMAIL__DEFAULT_SENDER", "Test Sender <test@example.com>")
    monkeypatch.setenv("EMAIL__RESEND__API_KEY", "test-resend-key")
