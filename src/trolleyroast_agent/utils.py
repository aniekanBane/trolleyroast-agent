from datetime import UTC, datetime


def utc_now() -> datetime:
    """Returns the current datetime in UTC."""
    return datetime.now(UTC)
