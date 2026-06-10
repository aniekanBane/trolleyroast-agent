from pathlib import Path

import pytest

from trolleyroast_agent.core.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Automatically clear settings cache before every test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_logs_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the logs file path."""
    monkeypatch.setenv("LOGGING_FILE_DIRECTORY", str(tmp_path))


@pytest.fixture
def mock_state_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock the state file path."""
    path = tmp_path / "trolleyroast-state.json"
    monkeypatch.setenv("STATE_FILE_PATH", str(path))
    return path
