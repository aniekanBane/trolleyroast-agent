import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from trolleyroast_agent.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EmailBody:
    """Represents the body content of an email."""

    html: str
    plain_text: str


class EmailDeliveryError(Exception):
    """Raised when an email client fails to transmit a message."""


class EmailClientProto(Protocol):
    """Defines a protocol for email clients."""

    async def send_email(
        self,
        *,
        sender: str | None = None,
        recipients: Sequence[str],
        subject: str,
        body: EmailBody,
        ccs: Sequence[str] = (),
        bccs: Sequence[str] = (),
        reply_to: str | None = None,
    ) -> None: ...


def _get_sender(sender: str | None = None) -> str:
    settings = get_settings()

    sender = sender or settings.email.default_sender
    if not sender:
        raise ValueError("No sender is configured.")

    return sender


class ResendEmailClient(EmailClientProto):
    """Resend email client implementation."""

    def __init__(self):
        import resend

        settings = get_settings()
        resend_settings = settings.email.resend
        if resend_settings is None:
            raise RuntimeError("Resend email settings are not configured.")

        resend.api_key = resend_settings.api_key

    async def send_email(
        self,
        *,
        sender: str | None = None,
        recipients: Sequence[str],
        subject: str,
        body: EmailBody,
        ccs: Sequence[str] = (),
        bccs: Sequence[str] = (),
        reply_to: str | None = None,
    ) -> None:
        import resend

        msg: resend.Emails.SendParams = {
            "from": _get_sender(sender),
            "to": list(recipients),
            "subject": subject,
            "html": body.html,
            "text": body.plain_text,
        }

        if ccs:
            msg["cc"] = list(ccs)

        if bccs:
            msg["bcc"] = list(bccs)

        if reply_to:
            msg["reply_to"] = reply_to

        log_extra = {"client": "resend", "to": recipients}

        try:
            response = await resend.Emails.send_async(msg)
            logger.debug("Email sent: %s", response["id"], extra=log_extra)
        except Exception as e:
            logger.error("Failed to send email", extra=log_extra)
            raise EmailDeliveryError("Failed to send email via Resend.") from e


class SmtpEmailClient(EmailClientProto):
    """SMTP email client implementation."""

    async def send_email(
        self,
        *,
        sender: str | None = None,
        recipients: Sequence[str],
        subject: str,
        body: EmailBody,
        ccs: Sequence[str] = (),
        bccs: Sequence[str] = (),
        reply_to: str | None = None,
    ) -> None:
        import smtplib
        from email.message import EmailMessage

        settings = get_settings()
        smtp_settings = settings.email.smtp
        if smtp_settings is None:
            raise RuntimeError("SMTP email settings are not configured.")

        msg = EmailMessage()
        msg["From"] = _get_sender(sender)
        msg["To"] = ",".join(recipients)
        msg["Subject"] = subject

        if ccs:
            msg["Cc"] = ",".join(ccs)

        if reply_to:
            msg["Reply-To"] = reply_to

        all_recipients = list(recipients) + list(ccs) + list(bccs)

        msg.set_content(body.plain_text)
        msg.add_alternative(body.html, subtype="html")

        log_extra = {"client": "smtp", "to": all_recipients}

        try:

            def _send():
                with smtplib.SMTP(smtp_settings.host, smtp_settings.port) as server:
                    server.ehlo()

                    if smtp_settings.require_tls:
                        server.starttls()
                        server.ehlo()

                    if smtp_settings.username and smtp_settings.password:
                        server.login(smtp_settings.username, smtp_settings.password)
                        server.ehlo()

                    server.send_message(msg, to_addrs=all_recipients)
                    logger.debug("Email sent", extra=log_extra)

            await asyncio.to_thread(_send)
        except Exception as e:
            logger.error("Failed to send email", extra=log_extra)
            raise EmailDeliveryError("Failed to send email via SMTP.") from e


def get_email_client() -> EmailClientProto:
    """Factory: create email client from settings."""
    settings = get_settings()
    provider = settings.email.provider
    match provider:
        case "resend":
            return ResendEmailClient()
        case "smtp":
            return SmtpEmailClient()
        case _:
            raise ValueError(f"Unknown email provider: {provider}")


if __name__ == "__main__":
    client = get_email_client()

    asyncio.run(
        client.send_email(
            recipients=["Dr Tosin <dioscuri@gmail.com>"],
            subject="Test Send Email",
            body=EmailBody(html="<h1>Test Email</h1>", plain_text="Test Email"),
        )
    )
