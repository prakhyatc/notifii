from __future__ import annotations

import os

from .base import DeliveryResult, EmailAdapter, EmailPayload


class ResendEmailAdapter(EmailAdapter):
    """Delivers email via Resend (https://resend.com) free tier."""

    provider_name = "resend"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("RESEND_API_KEY", "")

    async def send(self, payload: EmailPayload) -> DeliveryResult:
        try:
            import resend as resend_sdk

            resend_sdk.api_key = self._api_key
            params: resend_sdk.Emails.SendParams = {
                "from": payload.from_address,
                "to": [payload.to],
                "subject": payload.subject,
                "text": payload.body,
                "headers": {"X-Notifii-Message-Id": payload.message_id},
            }
            resp = resend_sdk.Emails.send(params)
            return DeliveryResult(
                success=True,
                provider=self.provider_name,
                provider_message_id=resp.get("id"),
            )
        except Exception as exc:
            return DeliveryResult(
                success=False,
                provider=self.provider_name,
                error=str(exc),
            )
