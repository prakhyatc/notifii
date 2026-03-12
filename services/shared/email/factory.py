from __future__ import annotations

import os

from .base import EmailAdapter


def create_email_adapter() -> EmailAdapter:
    """Instantiate the correct email provider based on EMAIL_PROVIDER env var."""
    provider = os.getenv("EMAIL_PROVIDER", "console").lower()

    if provider == "console":
        from .console_adapter import ConsoleEmailAdapter

        return ConsoleEmailAdapter()

    if provider == "smtp":
        from .smtp_adapter import SMTPEmailAdapter

        return SMTPEmailAdapter()

    if provider == "resend":
        from .resend_adapter import ResendEmailAdapter

        return ResendEmailAdapter()

    if provider == "ses":
        from .ses_adapter import SESEmailAdapter

        return SESEmailAdapter()

    raise ValueError(f"Unknown EMAIL_PROVIDER: {provider!r}. Supported: console, smtp, resend, ses")
