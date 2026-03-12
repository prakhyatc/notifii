from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .base import QueueAdapter, QueueMessage


class SQSAdapter(QueueAdapter):
    """AWS SQS implementation of the queue interface."""

    def __init__(self, queue_url: str, region: str = "us-east-1") -> None:
        self._queue_url = queue_url
        self._client = boto3.client("sqs", region_name=region)

    async def send(self, message: dict[str, Any], attributes: dict[str, str] | None = None) -> str:
        kwargs: dict[str, Any] = {
            "QueueUrl": self._queue_url,
            "MessageBody": json.dumps(message, separators=(",", ":"), ensure_ascii=False),
        }
        if attributes:
            kwargs["MessageAttributes"] = {
                k: {"DataType": "String", "StringValue": v} for k, v in attributes.items()
            }
        try:
            resp = self._client.send_message(**kwargs)
            return resp["MessageId"]
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"SQS send failed: {exc}") from exc

    async def receive(self, max_messages: int = 10, wait_seconds: int = 20) -> list[QueueMessage]:
        try:
            resp = self._client.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=min(max_messages, 10),
                WaitTimeSeconds=wait_seconds,
                MessageAttributeNames=["All"],
                AttributeNames=["All"],
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"SQS receive failed: {exc}") from exc

        out: list[QueueMessage] = []
        for m in resp.get("Messages", []):
            body = json.loads(m["Body"])
            out.append(
                QueueMessage(
                    body=body,
                    receipt_handle=m["ReceiptHandle"],
                    raw_attributes=m.get("MessageAttributes"),
                )
            )
        return out

    async def delete(self, receipt_handle: str) -> None:
        try:
            self._client.delete_message(QueueUrl=self._queue_url, ReceiptHandle=receipt_handle)
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"SQS delete failed: {exc}") from exc

    async def queue_depth(self) -> int:
        try:
            resp = self._client.get_queue_attributes(
                QueueUrl=self._queue_url,
                AttributeNames=["ApproximateNumberOfMessages"],
            )
            return int(resp["Attributes"].get("ApproximateNumberOfMessages", 0))
        except (BotoCoreError, ClientError):
            return -1
