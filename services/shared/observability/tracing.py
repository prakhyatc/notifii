"""OpenTelemetry distributed tracing for Notifii.

Enabled via OTEL_ENABLED=true. When disabled, all helpers are safe no-ops.

Trace context flows:
  Client → API (auto-instrumented) → queue message metadata → Worker spans → email delivery spans

The trace context is serialized as a W3C `traceparent` header into the queue
message body so the worker can restore the parent span and continue the trace.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator

_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"

_tracer = None  # lazy singleton


def _get_tracer():
    global _tracer
    if _tracer is not None:
        return _tracer
    if not _ENABLED:
        return None
    try:
        from opentelemetry import trace

        _tracer = trace.get_tracer("notifii", "2.0.0")
        return _tracer
    except ImportError:
        return None


def init_tracing(service_name: str) -> None:
    """Bootstrap the OTEL SDK with OTLP exporter. Call once at service startup."""
    if not _ENABLED:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)

        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)

        global _tracer
        _tracer = trace.get_tracer("notifii", "2.0.0")
    except ImportError:
        pass


def instrument_fastapi(app) -> None:
    """Auto-instrument a FastAPI application with OTEL."""
    if not _ENABLED:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="health,ready,metrics",
        )
    except ImportError:
        pass


def inject_trace_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Inject the current W3C trace context into a queue message payload.

    Adds a `_trace_context` dict with `traceparent` (and optionally `tracestate`)
    so the consuming worker can restore the trace.
    """
    if not _ENABLED:
        return payload
    try:
        from opentelemetry.context import get_current
        from opentelemetry.propagators.textmap import DictGetter
        from opentelemetry import propagate

        carrier: dict[str, str] = {}
        propagate.inject(carrier)
        if carrier:
            payload["_trace_context"] = carrier
    except ImportError:
        pass
    return payload


def extract_trace_context(payload: dict[str, Any]):
    """Extract W3C trace context from a queue message payload.

    Returns an OTEL context object that should be used as the parent context
    for worker spans. Returns None if tracing is disabled or no context found.
    """
    if not _ENABLED:
        return None
    try:
        from opentelemetry import propagate

        carrier = payload.get("_trace_context")
        if not carrier or not isinstance(carrier, dict):
            return None
        return propagate.extract(carrier)
    except ImportError:
        return None


def get_current_trace_id() -> str | None:
    """Return the current trace ID as a hex string, or None."""
    if not _ENABLED:
        return None
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            return format(ctx.trace_id, "032x")
    except ImportError:
        pass
    return None


@contextmanager
def start_span(
    name: str,
    kind: str = "internal",
    attributes: dict[str, Any] | None = None,
    parent_context=None,
) -> Generator:
    """Create an OTEL span. Falls back to a no-op if tracing is disabled.

    Usage::

        with start_span("process_message", attributes={"message_id": mid}) as span:
            ...
            span.set_attribute("delivery.provider", "resend")
    """
    if not _ENABLED:
        yield _NoOpSpan()
        return

    tracer = _get_tracer()
    if tracer is None:
        yield _NoOpSpan()
        return

    try:
        from opentelemetry import trace, context

        kind_map = {
            "internal": trace.SpanKind.INTERNAL,
            "server": trace.SpanKind.SERVER,
            "client": trace.SpanKind.CLIENT,
            "producer": trace.SpanKind.PRODUCER,
            "consumer": trace.SpanKind.CONSUMER,
        }
        span_kind = kind_map.get(kind, trace.SpanKind.INTERNAL)

        ctx = parent_context if parent_context else None
        if ctx:
            token = context.attach(ctx)

        with tracer.start_as_current_span(
            name,
            kind=span_kind,
            attributes=attributes or {},
        ) as span:
            yield span

        if ctx:
            context.detach(token)
    except Exception:
        yield _NoOpSpan()


class _NoOpSpan:
    """Placeholder when tracing is disabled."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, *args, **kwargs) -> None:
        pass

    def record_exception(self, exc: Exception) -> None:
        pass

    def add_event(self, name: str, attributes: dict | None = None) -> None:
        pass
