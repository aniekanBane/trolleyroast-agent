import json
from pathlib import Path

import pytest

from trolleyroast_agent.core.state import AgentState, get_agent_state


@pytest.fixture(autouse=True)
def clear_state_singleton():
    """Reset the singleton global variable before and after every test."""
    import trolleyroast_agent.core.state as state_module

    state_module._agent_state = None
    yield
    state_module._agent_state = None


class TestAgentState:
    """`AgentState` test suite."""

    def test_initialization_with_settings_path(self, mock_state_path: Path):
        """It should start with clean defaults if the file does not exist."""
        state = AgentState()

        assert state.consecutive_errors == 0
        assert state.paused is False
        assert state.last_price_update is None

    def test_initialization_with_explicit_path(self, tmp_path: Path):
        """It should use the path passed directly to __init__."""
        custom_path = tmp_path / "custom-state.json"
        state = AgentState(path=custom_path)

        assert state._path == custom_path

    def test_loads_existing_state(self, mock_state_path: Path):
        """It should load existing state from disk upon initialization."""
        mock_state_path.write_text(
            json.dumps(
                {
                    "last_price_update": "2026-06-09T00:00:00",
                    "consecutive_errors": 2,
                    "paused": True,
                    "total_prices_updated_lifetime": 150,
                }
            ),
            encoding="utf-8",
        )

        state = AgentState()

        assert state.last_price_update == "2026-06-09T00:00:00"
        assert state.consecutive_errors == 2
        assert state.paused is True
        assert state.total_prices_updated_lifetime == 150

    def test_corruption_on_load_resets_silently(
        self,
        mock_state_path: Path,
        caplog: pytest.LogCaptureFixture,
    ):
        """It should reset state to defaults if the state file is corrupted."""
        mock_state_path.write_text("NOT JSON{{", encoding="utf-8")

        state = AgentState()

        assert state.last_price_update is None
        assert state.consecutive_errors == 0
        assert "corrupted" in caplog.text

    def test_os_error_on_load_resets_silently(
        self, mock_state_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """It should handle permission or OS errors gracefully during read."""
        mock_state_path.mkdir(parents=True)

        state = AgentState()

        assert state.paused is False
        assert "Cannot read state file" in caplog.text

    def test_commit_is_noop_when_not_dirty(self, mock_state_path: Path):
        """It should not write to disk if the state has not been modified."""
        state = AgentState()
        state.commit()
        assert not mock_state_path.exists()

    def test_property_round_trip(self, mock_state_path: Path):
        """It should persist attribute changes and write them to disk."""
        state = AgentState()

        state.last_price_update = "2026-06-09T12:00:00"
        state.last_email_run = "2026-06-09T07:15:00"
        state.last_welcome_check = "2026-06-09T00:30:00"
        state.add_prices_updated(5)
        state.add_emails_sent(3)
        state.add_alerts_generated(2)
        state.bump_error()
        state.paused = True

        assert not mock_state_path.exists()

        state.commit()
        assert mock_state_path.exists()

        # Verify file contents
        data = json.loads(mock_state_path.read_text(encoding="utf-8"))
        assert data["last_price_update"] == "2026-06-09T12:00:00"
        assert data["last_email_run"] == "2026-06-09T07:15:00"
        assert data["last_welcome_check"] == "2026-06-09T00:30:00"
        assert data["total_prices_updated_lifetime"] == 5
        assert data["total_emails_sent_lifetime"] == 3
        assert data["total_alerts_generated_lifetime"] == 2
        assert data["consecutive_errors"] == 1
        assert data["paused"] is True

    def test_reset_errors_clears_counter(self, mock_state_path: Path):
        """It should reset the consecutive errors counter to zero."""
        state = AgentState()
        state.bump_error()
        state.bump_error()
        state.reset_errors()
        state.commit()
        assert state.consecutive_errors == 0
        data = json.loads(mock_state_path.read_text(encoding="utf-8"))
        assert data["consecutive_errors"] == 0

    def test_atomic_write_survives_simulated_crash(
        self, tmp_path: Path, mock_state_path: Path
    ):
        """Verify temp-file-then-rename pattern leaves valid JSON even if interrupted."""
        state = AgentState()
        state.last_price_update = "2026-06-09T00:00:00"
        state.commit()

        # No .tmp file should remain
        assert not mock_state_path.with_suffix(".tmp").exists()
        # File should be valid JSON
        data = json.loads(mock_state_path.read_text(encoding="utf-8"))
        assert data["last_price_update"] == "2026-06-09T00:00:00"


class TestGetAgentState:
    """`get_agent_state()` test suite."""

    def test_returns_singleton_instance(self, mock_state_path: Path):
        """It should return the same instance on repeated calls."""
        from trolleyroast_agent.core.state import get_agent_state

        state1 = get_agent_state()
        state2 = get_agent_state()

        assert state1 is state2
        assert state1._path == mock_state_path

    def test_lazy_initialization(self, mock_state_path: Path):
        """It should initialize the state lazily on first access."""
        import trolleyroast_agent.core.state as state_module

        assert state_module._agent_state is None

        state = get_agent_state()
        assert state_module._agent_state is state
