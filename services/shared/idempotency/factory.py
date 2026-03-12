from __future__ import annotations

import os

from .base import IdempotencyStore


def create_idempotency_store() -> IdempotencyStore:
    """Instantiate the correct idempotency backend based on IDEMPOTENCY_BACKEND env var."""
    backend = os.getenv("IDEMPOTENCY_BACKEND", "redis").lower()

    if backend == "memory":
        from .memory_store import MemoryIdempotencyStore

        return MemoryIdempotencyStore()

    if backend == "redis":
        from .redis_store import RedisIdempotencyStore

        return RedisIdempotencyStore()

    raise ValueError(f"Unknown IDEMPOTENCY_BACKEND: {backend!r}. Supported: memory, redis")
