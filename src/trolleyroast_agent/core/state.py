"""Local JSON state persistence."""

import json
import logging
from pathlib import Path
from typing import Any

from .config import get_settings

logger = logging.getLogger(__name__)


class AgentState:
    """Mutable state container backed by a JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        """Initialize the agent state.

        Args:
            path: Path to the state file. If None, use the default path from settings.
        """
        self._path = path or get_settings().state_file_path
        self._data: dict[str, Any] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._data = {}
            return

        try:
            self._data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.warning(
                "State file corrupted at %s, resetting: %s", self._path, str(e)
            )
            self._data = {}
        except OSError as e:
            logger.error("Cannot read state file %s: %s", self._path, str(e))
            self._data = {}

    def _touch(self) -> None:
        self._dirty = True

    def commit(self) -> None:
        """Persist all in-memory state to disk if dirty."""
        if not self._dirty:
            return

        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(".tmp")
        try:
            temp.write_text(
                json.dumps(self._data, indent=2, default=str),
                encoding="utf-8",
            )
            temp.replace(self._path)
            self._dirty = False
        except OSError as e:
            logger.error("Failed to write state file: %s", str(e))

    # --- accessors ---

    @property
    def last_price_update(self) -> str | None:
        return self._data.get("last_price_update")

    @last_price_update.setter
    def last_price_update(self, value: str | None) -> None:
        self._data["last_price_update"] = value
        self._touch()

    @property
    def last_email_run(self) -> str | None:
        return self._data.get("last_email_run")

    @last_email_run.setter
    def last_email_run(self, value: str | None) -> None:
        self._data["last_email_run"] = value
        self._touch()

    @property
    def last_welcome_check(self) -> str | None:
        return self._data.get("last_welcome_check")

    @last_welcome_check.setter
    def last_welcome_check(self, value: str | None) -> None:
        self._data["last_welcome_check"] = value
        self._touch()

    @property
    def total_prices_updated_lifetime(self) -> int:
        return self._data.get("total_prices_updated_lifetime", 0)

    def add_prices_updated(self, n: int) -> None:
        self._data["total_prices_updated_lifetime"] = (
            self.total_prices_updated_lifetime + n
        )
        self._touch()

    @property
    def total_alerts_generated_lifetime(self) -> int:
        return self._data.get("total_alerts_generated_lifetime", 0)

    def add_alerts_generated(self, n: int) -> None:
        self._data["total_alerts_generated_lifetime"] = (
            self.total_alerts_generated_lifetime + n
        )
        self._touch()

    @property
    def total_emails_sent_lifetime(self) -> int:
        return self._data.get("total_emails_sent_lifetime", 0)

    def add_emails_sent(self, n: int) -> None:
        self._data["total_emails_sent_lifetime"] = self.total_emails_sent_lifetime + n
        self._touch()

    @property
    def consecutive_errors(self) -> int:
        return self._data.get("consecutive_errors", 0)

    def bump_error(self) -> int:
        self._data["consecutive_errors"] = self.consecutive_errors + 1
        self._touch()
        return self.consecutive_errors

    def reset_errors(self) -> None:
        self._data["consecutive_errors"] = 0
        self._touch()

    @property
    def paused(self) -> bool:
        return self._data.get("paused", False)

    @paused.setter
    def paused(self, value: bool) -> None:
        self._data["paused"] = value
        self._touch()


_agent_state: AgentState | None = None


def get_agent_state() -> AgentState:
    """Return the singleton agent state instance."""
    global _agent_state
    if _agent_state is None:
        _agent_state = AgentState()
    return _agent_state
