from __future__ import annotations

import json
import os

import redis.asyncio as aioredis

from .base import IdempotencyRecord, IdempotencyStore, MessageStatus

_KEY_PREFIX = "notifii:idempotency:"


class RedisIdempotencyStore(IdempotencyStore):
    """Redis-backed idempotency store with TTL-based expiry."""

    def __init__(
        self,
        redis_url: str | None = None,
        ttl_seconds: int = 86400,
    ) -> None:
        url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis: aioredis.Redis = aioredis.from_url(url, decode_responses=True)
        self._ttl = ttl_seconds

    def _key(self, idempotency_key: str) -> str:
        return f"{_KEY_PREFIX}{idempotency_key}"

    async def check_and_set(self, key: str, message_id: str) -> IdempotencyRecord | None:
        rkey = self._key(key)
        record_data = {
            "idempotency_key": key,
            "message_id": message_id,
            "status": MessageStatus.QUEUED.value,
        }
        payload = json.dumps(record_data, separators=(",", ":"))

        was_set = await self._redis.set(rkey, payload, nx=True, ex=self._ttl)
        if was_set:
            return None

        existing_raw = await self._redis.get(rkey)
        if existing_raw:
            data = json.loads(existing_raw)
            return IdempotencyRecord(
                idempotency_key=data["idempotency_key"],
                message_id=data["message_id"],
                status=MessageStatus(data["status"]),
                ttl_seconds=self._ttl,
            )
        return None

    async def get(self, key: str) -> IdempotencyRecord | None:
        raw = await self._redis.get(self._key(key))
        if not raw:
            return None
        data = json.loads(raw)
        return IdempotencyRecord(
            idempotency_key=data["idempotency_key"],
            message_id=data["message_id"],
            status=MessageStatus(data["status"]),
            ttl_seconds=self._ttl,
        )

    async def update_status(self, key: str, status: MessageStatus) -> None:
        rkey = self._key(key)
        raw = await self._redis.get(rkey)
        if not raw:
            return
        data = json.loads(raw)
        data["status"] = status.value
        ttl = await self._redis.ttl(rkey)
        if ttl < 0:
            ttl = self._ttl
        await self._redis.set(rkey, json.dumps(data, separators=(",", ":")), ex=ttl)

    async def close(self) -> None:
        await self._redis.aclose()
