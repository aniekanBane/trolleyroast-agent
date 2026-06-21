import pytest

from trolleyroast_agent.clients.emails import (
    ResendEmailClient,
    SmtpEmailClient,
    get_email_client,
)


class TestGetEmailClientFactory:
    """Verify factory creates functional clients from real settings."""

    def test_returns_resend_client_when_provider(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("EMAIL__PROVIDER", "resend")
        monkeypatch.setenv("EMAIL__RESEND__API_KEY", "resend-api-key")
        client = get_email_client()
        assert isinstance(client, ResendEmailClient)

    def test_returns_smtp_client_when_provider(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("EMAIL__PROVIDER", "smtp")
        client = get_email_client()
        assert isinstance(client, SmtpEmailClient)
