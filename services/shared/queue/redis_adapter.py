from __future__ import annotations

import json
import time
import asyncio
from typing import Any

import redis.asyncio as aioredis

from .base import QueueAdapter, QueueMessage

_DEFAULT_STREAM = "notifii:notifications"
_DEFAULT_GROUP = "workers"
_DEFAULT_DLQ_STREAM = "notifii:notifications:dlq"
_MAX_RETRIES = 5


class RedisQueueAdapter(QueueAdapter):
    """Redis Streams implementation of the queue interface.

    Uses a consumer group so multiple workers can share the load,
    and pending-entry tracking gives us visibility-timeout semantics
    similar to SQS.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        stream: str = _DEFAULT_STREAM,
        group: str = _DEFAULT_GROUP,
        consumer: str = "worker-1",
        dlq_stream: str = _DEFAULT_DLQ_STREAM,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        self._redis: aioredis.Redis = aioredis.from_url(redis_url, decode_responses=True)
        self._stream = stream
        self._group = group
        self._consumer = consumer
        self._dlq_stream = dlq_stream
        self._max_retries = max_retries
        self._group_ready = False

    async def _ensure_group(self) -> None:
        if self._group_ready:
            return
        try:
            await self._redis.xgroup_create(self._stream, self._group, id="0", mkstream=True)
        except aioredis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        self._group_ready = True

    async def send(self, message: dict[str, Any], attributes: dict[str, str] | None = None) -> str:
        payload = {"data": json.dumps(message, separators=(",", ":"), ensure_ascii=False)}
        if attributes:
            payload["attrs"] = json.dumps(attributes, separators=(",", ":"))
        msg_id: str = await self._redis.xadd(self._stream, payload)
        return msg_id

    async def receive(self, max_messages: int = 10, wait_seconds: int = 20) -> list[QueueMessage]:
        await self._ensure_group()

        await self._claim_stale_messages()

        raw = await self._redis.xreadgroup(
            groupname=self._group,
            consumername=self._consumer,
            streams={self._stream: ">"},
            count=max_messages,
            block=wait_seconds * 1000,
        )

        out: list[QueueMessage] = []
        for _stream_name, entries in raw:
            for entry_id, fields in entries:
                body = json.loads(fields["data"])
                out.append(
                    QueueMessage(
                        body=body,
                        receipt_handle=entry_id,
                        raw_attributes=json.loads(fields["attrs"]) if "attrs" in fields else None,
                    )
                )
        return out

    async def _claim_stale_messages(self) -> None:
        """Move messages that have been pending too long (>30s) back to this consumer,
        and route messages that exceeded max retries to the DLQ stream."""
        try:
            pending = await self._redis.xpending_range(
                self._stream, self._group, min="-", max="+", count=100,
            )
        except Exception:
            return

        for entry in pending:
            msg_id = entry["message_id"]
            times_delivered = entry.get("times_delivered", 1)
            idle_ms = entry.get("time_since_delivered", 0)

            if times_delivered >= self._max_retries:
                raw = await self._redis.xrange(self._stream, min=msg_id, max=msg_id)
                if raw:
                    _, fields = raw[0]
                    fields["original_id"] = msg_id
                    fields["failed_at"] = str(time.time())
                    await self._redis.xadd(self._dlq_stream, fields)
                await self._redis.xack(self._stream, self._group, msg_id)
                await self._redis.xdel(self._stream, msg_id)
            elif idle_ms > 30_000:
                await self._redis.xclaim(
                    self._stream, self._group, self._consumer, min_idle_time=30_000, message_ids=[msg_id],
                )

    async def delete(self, receipt_handle: str) -> None:
        await self._redis.xack(self._stream, self._group, receipt_handle)

    async def queue_depth(self) -> int:
        length = await self._redis.xlen(self._stream)
        return int(length)

    async def dlq_messages(self, count: int = 20) -> list[dict[str, Any]]:
        """Read recent DLQ entries for the admin dashboard."""
        raw = await self._redis.xrevrange(self._dlq_stream, count=count)
        out: list[dict[str, Any]] = []
        for entry_id, fields in raw:
            body = json.loads(fields.get("data", "{}"))
            out.append({"id": entry_id, "body": body, "failed_at": fields.get("failed_at")})
        return out

    async def retry_dlq_message(self, dlq_entry_id: str) -> str | None:
        """Move a DLQ message back to the main stream for reprocessing."""
        raw = await self._redis.xrange(self._dlq_stream, min=dlq_entry_id, max=dlq_entry_id)
        if not raw:
            return None
        _, fields = raw[0]
        fields.pop("original_id", None)
        fields.pop("failed_at", None)
        new_id = await self._redis.xadd(self._stream, fields)
        await self._redis.xdel(self._dlq_stream, dlq_entry_id)
        return new_id

    async def close(self) -> None:
        await self._redis.aclose()
