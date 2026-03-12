from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class EmailPayload:
    to: str
    subject: str
    body: str
    message_id: str
    from_address: str = "noreply@notifii.dev"


@dataclass
class DeliveryResult:
    success: bool
    provider: str
    provider_message_id: str | None = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)


class EmailAdapter(ABC):
    """Abstract interface for email delivery providers."""

    provider_name: str = "unknown"

    @abstractmethod
    async def send(self, payload: EmailPayload) -> DeliveryResult:
        """Send an email. Returns a DeliveryResult regardless of success/failure."""

    async def close(self) -> None:
        """Release provider resources."""
