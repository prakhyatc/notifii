from __future__ import annotations

import contextvars
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .metrics import metrics
from .tracing import get_current_trace_id

_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id_ctx.get("")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Injects X-Request-Id into every request/response and tracks HTTP metrics.

    When OpenTelemetry is active, the OTEL trace ID is preferred as the
    canonical request identifier so logs and traces correlate automatically.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or get_current_trace_id() or str(uuid4())
        _request_id_ctx.set(request_id)

        metrics.inc("http_requests_total")
        start = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"

        trace_id = get_current_trace_id()
        if trace_id:
            response.headers["X-Trace-Id"] = trace_id

        if response.status_code >= 400:
            metrics.inc("http_errors_total")

        return response
