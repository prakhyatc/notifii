from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

os.environ["QUEUE_BACKEND"] = "memory"
os.environ["IDEMPOTENCY_BACKEND"] = "memory"
os.environ["EMAIL_PROVIDER"] = "console"
os.environ["APP_ENV"] = "test"
os.environ["DEMO_MODE"] = "false"
os.environ["OTEL_ENABLED"] = "false"
