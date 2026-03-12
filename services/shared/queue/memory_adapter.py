from __future__ import annotations

import json
import time
from collections import deque
from typing import Any
from uuid import uuid4

from .base import QueueAdapter, QueueMessage

_MAX_RETRIES = 5


class MemoryQueueAdapter(QueueAdapter):
    """In-memory queue for unit testing. Not suitable for production."""

    def __init__(self) -> None:
        self._queue: deque[tuple[str, dict[str, Any], dict[str, str] | None]] = deque()
        self._dlq: list[dict[str, Any]] = []
        self._retry_counts: dict[str, int] = {}

    async def send(self, message: dict[str, Any], attributes: dict[str, str] | None = None) -> str:
        msg_id = str(uuid4())
        self._queue.append((msg_id, message, attributes))
        return msg_id

    async def receive(self, max_messages: int = 10, wait_seconds: int = 0) -> list[QueueMessage]:
        out: list[QueueMessage] = []
        for _ in range(min(max_messages, len(self._queue))):
            msg_id, body, attrs = self._queue.popleft()
            out.append(QueueMessage(body=body, receipt_handle=msg_id, raw_attributes=attrs))
        return out

    async def delete(self, receipt_handle: str) -> None:
        self._retry_counts.pop(receipt_handle, None)

    async def queue_depth(self) -> int:
        return len(self._queue)

    async def dlq_messages(self, count: int = 20) -> list[dict[str, Any]]:
        return self._dlq[:count]

    async def retry_dlq_message(self, dlq_entry_id: str) -> str | None:
        for i, entry in enumerate(self._dlq):
            if entry.get("id") == dlq_entry_id:
                self._dlq.pop(i)
                return await self.send(entry.get("body", {}))
        return None

    async def close(self) -> None:
        pass
