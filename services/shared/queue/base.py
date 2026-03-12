from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class QueueMessage:
    body: dict[str, Any]
    receipt_handle: str
    raw_attributes: dict[str, Any] | None = None


class QueueAdapter(ABC):
    """Abstract interface for durable message queues."""

    @abstractmethod
    async def send(self, message: dict[str, Any], attributes: dict[str, str] | None = None) -> str:
        """Enqueue a message. Returns a provider-specific message ID."""

    @abstractmethod
    async def receive(self, max_messages: int = 10, wait_seconds: int = 20) -> list[QueueMessage]:
        """Dequeue up to *max_messages*. Long-poll for *wait_seconds*."""

    @abstractmethod
    async def delete(self, receipt_handle: str) -> None:
        """Acknowledge (delete) a successfully processed message."""

    @abstractmethod
    async def queue_depth(self) -> int:
        """Return the approximate number of messages waiting."""

    async def close(self) -> None:
        """Release any resources held by the adapter."""
