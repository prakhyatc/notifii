from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText

from .base import DeliveryResult, EmailAdapter, EmailPayload


class SMTPEmailAdapter(EmailAdapter):
    """Delivers email via SMTP. Works with Mailhog, Gmail, or any SMTP relay."""

    provider_name = "smtp"

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool | None = None,
    ) -> None:
        self._host = host or os.getenv("SMTP_HOST", "localhost")
        self._port = port or int(os.getenv("SMTP_PORT", "1025"))
        self._username = username or os.getenv("SMTP_USERNAME", "")
        self._password = password or os.getenv("SMTP_PASSWORD", "")
        self._use_tls = use_tls if use_tls is not None else os.getenv("SMTP_USE_TLS", "false").lower() == "true"

    async def send(self, payload: EmailPayload) -> DeliveryResult:
        msg = MIMEText(payload.body, "plain")
        msg["Subject"] = payload.subject
        msg["From"] = payload.from_address
        msg["To"] = payload.to
        msg["X-Notifii-Message-Id"] = payload.message_id

        try:
            if self._use_tls:
                server = smtplib.SMTP(self._host, self._port, timeout=10)
                server.starttls()
            else:
                server = smtplib.SMTP(self._host, self._port, timeout=10)

            if self._username:
                server.login(self._username, self._password)

            server.sendmail(payload.from_address, [payload.to], msg.as_string())
            server.quit()

            return DeliveryResult(
                success=True,
                provider=self.provider_name,
                provider_message_id=msg["Message-ID"],
            )
        except Exception as exc:
            return DeliveryResult(
                success=False,
                provider=self.provider_name,
                error=str(exc),
            )
