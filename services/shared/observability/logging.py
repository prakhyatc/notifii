from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StructuredLogger:
    """JSON structured logger for consistent observability across services.

    Automatically includes the OTEL trace_id and span_id when tracing is active.
    """

    def __init__(self, service: str, env: str | None = None) -> None:
        self.service = service
        self.env = env or os.getenv("APP_ENV", "dev")
        self._logger = logging.getLogger(f"notifii.{service}")
        self._logger.setLevel(logging.DEBUG)
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
        self._logger.propagate = False

    def _emit(self, level: str, event: str, **fields: Any) -> None:
        payload: dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "level": level,
            "service": self.service,
            "env": self.env,
            "event": event,
        }

        try:
            from .tracing import get_current_trace_id

            tid = get_current_trace_id()
            if tid:
                payload["trace_id"] = tid
        except Exception:
            pass

        payload.update(fields)
        line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False, default=str)
        if level == "ERROR":
            self._logger.error(line)
        elif level == "WARN":
            self._logger.warning(line)
        elif level == "DEBUG":
            self._logger.debug(line)
        else:
            self._logger.info(line)

    def info(self, event: str, **fields: Any) -> None:
        self._emit("INFO", event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self._emit("ERROR", event, **fields)

    def warn(self, event: str, **fields: Any) -> None:
        self._emit("WARN", event, **fields)

    def debug(self, event: str, **fields: Any) -> None:
        self._emit("DEBUG", event, **fields)
