from __future__ import annotations

import time
from typing import Dict

from .base import IdempotencyRecord, IdempotencyStore, MessageStatus


class MemoryIdempotencyStore(IdempotencyStore):
    """In-memory idempotency store. Suitable for single-process dev/testing."""

    def __init__(self, ttl_seconds: int = 86400) -> None:
        self._store: Dict[str, tuple[IdempotencyRecord, float]] = {}
        self._ttl = ttl_seconds

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, (_, ts) in self._store.items() if now - ts > self._ttl]
        for k in expired:
            del self._store[k]

    async def check_and_set(self, key: str, message_id: str) -> IdempotencyRecord | None:
        self._evict_expired()
        if key in self._store:
            return self._store[key][0]
        record = IdempotencyRecord(
            idempotency_key=key,
            message_id=message_id,
            status=MessageStatus.QUEUED,
            ttl_seconds=self._ttl,
        )
        self._store[key] = (record, time.time())
        return None

    async def get(self, key: str) -> IdempotencyRecord | None:
        self._evict_expired()
        entry = self._store.get(key)
        return entry[0] if entry else None

    async def update_status(self, key: str, status: MessageStatus) -> None:
        if key in self._store:
            record, ts = self._store[key]
            record.status = status
            self._store[key] = (record, ts)
