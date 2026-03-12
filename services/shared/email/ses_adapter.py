from __future__ import annotations

import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .base import DeliveryResult, EmailAdapter, EmailPayload


class SESEmailAdapter(EmailAdapter):
    """Delivers email via AWS SES."""

    provider_name = "ses"

    def __init__(self, region: str | None = None) -> None:
        self._region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = boto3.client("ses", region_name=self._region)

    async def send(self, payload: EmailPayload) -> DeliveryResult:
        try:
            resp = self._client.send_email(
                Source=payload.from_address,
                Destination={"ToAddresses": [payload.to]},
                Message={
                    "Subject": {"Data": payload.subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": payload.body, "Charset": "UTF-8"}},
                },
                Tags=[{"Name": "notifii_message_id", "Value": payload.message_id}],
            )
            return DeliveryResult(
                success=True,
                provider=self.provider_name,
                provider_message_id=resp["MessageId"],
            )
        except (BotoCoreError, ClientError) as exc:
            return DeliveryResult(
                success=False,
                provider=self.provider_name,
                error=str(exc),
            )
