from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class MessageStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass
class IdempotencyRecord:
    idempotency_key: str
    message_id: str
    status: MessageStatus
    ttl_seconds: int = 86400  # 24h default


class IdempotencyStore(ABC):
    """Abstract interface for idempotency deduplication."""

    @abstractmethod
    async def check_and_set(self, key: str, message_id: str) -> IdempotencyRecord | None:
        """Atomically check if key exists. If not, store it and return None.
        If it already exists, return the existing record (duplicate detected)."""

    @abstractmethod
    async def get(self, key: str) -> IdempotencyRecord | None:
        """Retrieve a record by idempotency key."""

    @abstractmethod
    async def update_status(self, key: str, status: MessageStatus) -> None:
        """Update the status of an existing record."""

    async def close(self) -> None:
        """Release resources."""
