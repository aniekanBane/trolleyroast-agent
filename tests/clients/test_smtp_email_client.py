import asyncio
from collections.abc import Iterator
from email import message_from_bytes
from email.message import Message as EmailMessage
from typing import Any

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message as MessageHandler

from trolleyroast_agent.clients.emails import (
    EmailBody,
    EmailDeliveryError,
    SmtpEmailClient,
)


def _make_body(**kwargs) -> EmailBody:
    defaults = {"html": "<h1>Hello</h1>", "plain_text": "Hello"}
    defaults.update(kwargs)
    return EmailBody(**defaults)


class _RecordingMessageHandler(MessageHandler):
    """Captures all received messages in a list for test inspection."""

    def __init__(self):
        super().__init__()
        self.messages: list[tuple[str, str, bytes]] = []

    def handle_message(self, message: EmailMessage):
        mail_from = message["X-MailFrom"]
        rcpt_to = message["X-RcptTo"]
        content = message.as_bytes()
        self.messages.append((mail_from, rcpt_to, content))


class TestSmtpEmailClientIntegration:
    """Test SMTP client against a real local SMTP server"""

    @pytest.fixture
    def smtp_server(self) -> Iterator[dict[str, Any]]:
        """Start a real SMTP server with in-memory message capture."""

        handler = _RecordingMessageHandler()
        controller = Controller(handler, hostname="localhost")

        controller.start()

        yield {
            "host": controller.hostname,
            "port": controller.port,
            "messages": handler.messages,
        }

        controller.stop()

    @pytest.fixture
    def smtp_email_client(self, smtp_server, monkeypatch: pytest.MonkeyPatch):
        """Configure SMTP client to connect to local test server."""
        monkeypatch.setenv("EMAIL__PROVIDER", "smtp")
        monkeypatch.setenv(
            "EMAIL__DEFAULT_SENDER", "TrolleyRoast <alerts@trolleyroast.app>"
        )
        monkeypatch.setenv("EMAIL__SMTP__HOST", smtp_server["host"])
        monkeypatch.setenv("EMAIL__SMTP__PORT", str(smtp_server["port"]))
        monkeypatch.setenv("EMAIL__SMTP__REQUIRE_TLS", "false")

        return SmtpEmailClient()

    @pytest.mark.asyncio
    async def test_delivers_email(
        self, smtp_email_client: SmtpEmailClient, smtp_server: dict[str, Any]
    ):
        """End-to-end: client → TCP → aiosmtpd → captured message."""
        body = _make_body()

        await smtp_email_client.send_email(
            recipients=["user@example.com"],
            subject="Integration SMTP Email Client Test",
            body=body,
            ccs=["cc1@example.com"],
            bccs=["bcc1@example.com"],
            reply_to="support@trolleyroast.app",
        )

        await asyncio.sleep(0.1)

        assert len(smtp_server["messages"]) == 1

        from_addr, rcpt_to, content = smtp_server["messages"][0]
        assert from_addr == "alerts@trolleyroast.app"
        assert "user@example.com" in rcpt_to
        assert "cc1@example.com" in rcpt_to
        assert "bcc1@example.com" in rcpt_to

        msg = message_from_bytes(content)
        assert msg["Subject"] == "Integration SMTP Email Client Test"
        assert msg["From"] == "TrolleyRoast <alerts@trolleyroast.app>"
        assert msg["To"] == "user@example.com"
        assert msg["Cc"] == "cc1@example.com"
        assert msg["Reply-To"] == "support@trolleyroast.app"

        parts = list(msg.walk())
        content_types = [p.get_content_type() for p in parts]
        assert "text/plain" in content_types
        assert "text/html" in content_types

    @pytest.mark.asyncio
    async def test_connection_refused_raises(self, monkeypatch: pytest.MonkeyPatch):
        """Verify connection failure raises `EmailDeliveryError`."""
        monkeypatch.setenv("EMAIL__PROVIDER", "smtp")
        monkeypatch.setenv(
            "EMAIL__DEFAULT_SENDER", "TrolleyRoast <alerts@trolleyroast.app>"
        )
        monkeypatch.setenv("EMAIL__SMTP__HOST", "localhost")
        monkeypatch.setenv("EMAIL__SMTP__PORT", "55507")

        client = SmtpEmailClient()

        with pytest.raises(EmailDeliveryError, match="Failed to send email via SMTP"):
            await client.send_email(
                recipients=["user@example.com"],
                subject="Fail Test",
                body=_make_body(),
            )
