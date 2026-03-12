from __future__ import annotations

import threading
import time
from typing import Any


class MetricsCollector:
    """Thread-safe in-process Prometheus-compatible metrics collector.

    Avoids external dependency on prometheus_client while still exposing
    /metrics in Prometheus text exposition format.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._help: dict[str, str] = {}
        self._types: dict[str, str] = {}

    def register_counter(self, name: str, help_text: str = "") -> None:
        with self._lock:
            self._counters.setdefault(name, 0.0)
            self._help[name] = help_text
            self._types[name] = "counter"

    def register_gauge(self, name: str, help_text: str = "") -> None:
        with self._lock:
            self._gauges.setdefault(name, 0.0)
            self._help[name] = help_text
            self._types[name] = "gauge"

    def inc(self, name: str, value: float = 1.0) -> None:
        with self._lock:
            if name in self._counters:
                self._counters[name] += value
            elif name in self._gauges:
                self._gauges[name] += value

    def dec(self, name: str, value: float = 1.0) -> None:
        with self._lock:
            if name in self._gauges:
                self._gauges[name] -= value

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def get(self, name: str) -> float:
        with self._lock:
            if name in self._counters:
                return self._counters[name]
            return self._gauges.get(name, 0.0)

    def snapshot(self) -> dict[str, Any]:
        """Return all metrics as a dict (for JSON /metrics endpoint)."""
        with self._lock:
            return {**self._counters, **self._gauges}

    def prometheus_text(self) -> str:
        """Render metrics in Prometheus text exposition format."""
        lines: list[str] = []
        with self._lock:
            all_metrics = {**self._counters, **self._gauges}
            for name, value in sorted(all_metrics.items()):
                if name in self._help:
                    lines.append(f"# HELP {name} {self._help[name]}")
                if name in self._types:
                    lines.append(f"# TYPE {name} {self._types[name]}")
                lines.append(f"{name} {value}")
        lines.append("")
        return "\n".join(lines)


metrics = MetricsCollector()

metrics.register_counter("notifications_received_total", "Total notification requests received")
metrics.register_counter("notifications_queued_total", "Total notifications successfully queued")
metrics.register_counter("notifications_processed_total", "Total notifications processed by workers")
metrics.register_counter("delivery_success_total", "Total successful email deliveries")
metrics.register_counter("delivery_failures_total", "Total failed email deliveries")
metrics.register_counter("idempotency_duplicates_total", "Total duplicate requests blocked")
metrics.register_gauge("queue_depth", "Approximate queue depth")
metrics.register_counter("http_requests_total", "Total HTTP requests")
metrics.register_counter("http_errors_total", "Total HTTP error responses")
