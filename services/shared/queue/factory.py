from __future__ import annotations

import os

from .base import QueueAdapter


def create_queue_adapter() -> QueueAdapter:
    """Instantiate the correct queue backend based on QUEUE_BACKEND env var."""
    backend = os.getenv("QUEUE_BACKEND", "redis").lower()

    if backend == "sqs":
        from .sqs_adapter import SQSAdapter

        queue_url = os.getenv("NOTIFII_QUEUE_URL")
        if not queue_url:
            raise RuntimeError("NOTIFII_QUEUE_URL is required when QUEUE_BACKEND=sqs")
        region = os.getenv("AWS_REGION", "us-east-1")
        return SQSAdapter(queue_url=queue_url, region=region)

    if backend == "redis":
        from .redis_adapter import RedisQueueAdapter

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        consumer_name = os.getenv("WORKER_CONSUMER_NAME", "worker-1")
        return RedisQueueAdapter(redis_url=redis_url, consumer=consumer_name)

    if backend == "memory":
        from .memory_adapter import MemoryQueueAdapter

        return MemoryQueueAdapter()

    raise ValueError(f"Unknown QUEUE_BACKEND: {backend!r}. Supported: sqs, redis, memory")
