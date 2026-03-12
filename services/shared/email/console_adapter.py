from __future__ import annotations

import json
import sys

from .base import DeliveryResult, EmailAdapter, EmailPayload


class ConsoleEmailAdapter(EmailAdapter):
    """Logs emails to stdout instead of sending. Ideal for local dev."""

    provider_name = "console"

    async def send(self, payload: EmailPayload) -> DeliveryResult:
        output = {
            "event": "email_console_delivery",
            "to": payload.to,
            "from": payload.from_address,
            "subject": payload.subject,
            "body_preview": payload.body[:200],
            "message_id": payload.message_id,
        }
        print(json.dumps(output, indent=2), file=sys.stdout, flush=True)
        return DeliveryResult(
            success=True,
            provider=self.provider_name,
            provider_message_id=f"console-{payload.message_id}",
        )
