from .base import EmailAdapter, EmailPayload, DeliveryResult
from .factory import create_email_adapter

__all__ = ["EmailAdapter", "EmailPayload", "DeliveryResult", "create_email_adapter"]
