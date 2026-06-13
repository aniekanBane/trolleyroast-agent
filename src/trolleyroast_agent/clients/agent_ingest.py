"""Supabase edge-function ingest client."""

import asyncio
import logging
from typing import Any, Literal

import httpx

from trolleyroast_agent.core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
RETRY_DELAY = 45.0

IngestAction = Literal[
    "health_check",
    "upsert_prices",
    "get_prices",
    "update_subscriber",
    "get_subscribers",
    "write_log",
]


class IngestError(Exception):
    """Raised when the ingest client fails to send a message."""


async def aingest(action: IngestAction, payload: dict[str, Any]) -> Any:
    """Call the Supabase agent-ingest edge function.

    Retries once on 5xx/timeout after 45 seconds.
    Raises on 401 (bad key) or repeated failure.

    Args:
        action: The action to perform
        payload: The payload to send to the edge function

    Returns:
        `Any`: The response from the edge function

    Raises:
        `ValueError`: If the agent key or anon key is not set
        `IngestError`: If the edge function request failed.
    """
    supabase_settings = get_settings().supabase

    if not supabase_settings.agent_key:
        raise ValueError("Missing edge function agent key.")

    if not supabase_settings.api_key:
        raise ValueError("Missing anon key.")

    body = {"action": action, "payload": payload}
    headers = {
        "Content-Type": "application/json",
        "apiKey": supabase_settings.api_key,
        "x-agent-key": supabase_settings.agent_key,
    }

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        response = await client.post(
            supabase_settings.ingest_url, headers=headers, json=body
        )

        # Retry once on server error, timeout, or rate limit
        if response.status_code >= 500 or response.status_code == 429:
            delay = RETRY_DELAY
            if response.status_code == 429:
                delay = float(response.headers.get("retry-after", RETRY_DELAY))

            logger.warning(
                "Ingest endpoint returned %d, retrying after %ds",
                response.status_code,
                delay,
                extra={"action": action, "payload": payload},
            )

            await asyncio.sleep(delay)
            response = await client.post(
                supabase_settings.ingest_url, headers=headers, json=body
            )

    if response.status_code == 401:
        raise IngestError("Ingest endpoint returned 401 — agent key invalid")

    if not response.is_success:
        logger.error(
            "Ingest action failed: %d %s",
            response.status_code,
            response.text,
            extra={"action": action, "payload": payload},
        )
        raise IngestError(
            f"Ingest endpoint returned {response.status_code}: {response.text}"
        )

    logger.debug(
        "Ingest action succeeded", extra={"action": action, "payload": payload}
    )

    return response.json()


if __name__ == "__main__":
    import pprint

    response = asyncio.run(aingest("health_check", {}))
    pprint.pp(response)
