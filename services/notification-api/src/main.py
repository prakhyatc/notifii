from __future__ import annotations

import json
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import FastAPI, Header, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from services.shared.queue import QueueAdapter, create_queue_adapter
from services.shared.idempotency import IdempotencyStore, create_idempotency_store
from services.shared.observability import (
    StructuredLogger,
    MetricsCollector,
    metrics,
    RequestIdMiddleware,
    get_request_id,
    init_tracing,
    instrument_fastapi,
    inject_trace_context,
    start_span,
    get_current_trace_id,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
APP_ENV = os.getenv("APP_ENV", "dev")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))

log = StructuredLogger("notification-api")

# ---------------------------------------------------------------------------
# Globals initialised in lifespan
# ---------------------------------------------------------------------------
queue: QueueAdapter | None = None
idempotency: IdempotencyStore | None = None

# Failure simulation flags (toggled via /internal endpoints)
_simulate_provider_failure = False
_simulate_slow_delivery = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global queue, idempotency
    init_tracing("notifii-api")
    queue = create_queue_adapter()
    idempotency = create_idempotency_store()
    log.info("api_started", queue_backend=os.getenv("QUEUE_BACKEND", "redis"), demo_mode=DEMO_MODE)
    yield
    if queue:
        await queue.close()
    if idempotency:
        await idempotency.close()
    log.info("api_stopped")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
Channel = Literal["email", "sms", "push"]


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    issue: str


class ErrorObject(BaseModel):
    code: str
    message: str
    details: Optional[List[ErrorDetail]] = None


class ErrorResponse(BaseModel):
    error: ErrorObject


class SendNotificationRequest(BaseModel):
    channel: Channel
    recipient: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=5000)
    idempotency_key: Optional[str] = Field(default=None, min_length=1)

    @field_validator("recipient")
    @classmethod
    def strip_recipient(cls, v: str) -> str:
        v2 = v.strip()
        if not v2:
            raise ValueError("recipient must not be empty")
        return v2

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        v2 = v.strip()
        if not v2:
            raise ValueError("message must not be empty")
        return v2


class SendNotificationResponse(BaseModel):
    message_id: str
    status: Literal["queued"]


# ---------------------------------------------------------------------------
# Simple in-memory rate limiter for demo mode
# ---------------------------------------------------------------------------
_rate_window: dict[str, list[float]] = {}


def _check_rate_limit(client_ip: str) -> bool:
    if not DEMO_MODE:
        return True
    now = time.time()
    window = _rate_window.setdefault(client_ip, [])
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= RATE_LIMIT_PER_MIN:
        return False
    window.append(now)
    return True


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Notifii Notification API",
    version="2.0.0",
    description="Cloud-agnostic, event-driven notification platform",
    lifespan=lifespan,
)

instrument_fastapi(app)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
@app.exception_handler(ValidationError)
async def pydantic_validation_error_handler(request: Request, exc: ValidationError):
    details = []
    for err in exc.errors():
        loc = err.get("loc", [])
        field = str(loc[-1]) if isinstance(loc, (list, tuple)) and len(loc) >= 2 else None
        details.append(ErrorDetail(field=field, issue=err.get("msg", "Invalid value")))

    body = ErrorResponse(
        error=ErrorObject(code="VALIDATION_ERROR", message="Request validation failed", details=details)
    ).model_dump()

    log.error("validation_error", trace_id=get_request_id(), path=str(request.url.path), detail_count=len(details))
    return JSONResponse(status_code=400, content=body)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    body = ErrorResponse(
        error=ErrorObject(code="INTERNAL_ERROR", message="Unexpected error occurred")
    ).model_dump()
    log.error(
        "unhandled_exception",
        trace_id=get_request_id(),
        path=str(request.url.path),
        exception_type=type(exc).__name__,
    )
    return JSONResponse(status_code=500, content=body)


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> Dict[str, str]:
    return {"status": "ready"}


# ---------------------------------------------------------------------------
# Metrics endpoint (Prometheus-compatible)
# ---------------------------------------------------------------------------
@app.get("/metrics")
async def metrics_endpoint():
    return PlainTextResponse(metrics.prometheus_text(), media_type="text/plain; version=0.0.4")


@app.get("/metrics/json")
async def metrics_json():
    return metrics.snapshot()


# ---------------------------------------------------------------------------
# Core endpoint: enqueue notification
# ---------------------------------------------------------------------------
@app.post("/v1/notifications:send", status_code=202)
async def send_notification(
    payload: SendNotificationRequest,
    request: Request,
    x_request_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    trace_id = x_request_id or get_request_id() or str(uuid4())
    metrics.inc("notifications_received_total")

    if not _check_rate_limit(request.client.host if request.client else "unknown"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded (demo mode)")

    if not queue:
        raise HTTPException(status_code=503, detail="Queue not initialised")

    message_id = str(uuid4())

    # Idempotency check
    if payload.idempotency_key and idempotency:
        existing = await idempotency.check_and_set(payload.idempotency_key, message_id)
        if existing:
            metrics.inc("idempotency_duplicates_total")
            log.info(
                "idempotency_duplicate",
                trace_id=trace_id,
                idempotency_key=payload.idempotency_key,
                original_message_id=existing.message_id,
            )
            return SendNotificationResponse(message_id=existing.message_id, status="queued").model_dump()

    queue_payload = inject_trace_context({
        "message_id": message_id,
        "request_id": trace_id,
        "channel": payload.channel,
        "recipient": payload.recipient,
        "message": payload.message,
        "idempotency_key": payload.idempotency_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "simulate_failure": _simulate_provider_failure,
        "simulate_slow": _simulate_slow_delivery,
    })

    try:
        await queue.send(queue_payload, attributes={"channel": payload.channel})
    except Exception as exc:
        log.error("queue_send_failed", trace_id=trace_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to enqueue notification")

    metrics.inc("notifications_queued_total")
    log.info(
        "notification_queued",
        trace_id=trace_id,
        message_id=message_id,
        channel=payload.channel,
        has_idempotency_key=bool(payload.idempotency_key),
    )

    return SendNotificationResponse(message_id=message_id, status="queued").model_dump()


# ---------------------------------------------------------------------------
# Admin / Dashboard API endpoints
# ---------------------------------------------------------------------------
@app.get("/v1/queue/depth")
async def queue_depth_endpoint():
    if not queue:
        raise HTTPException(status_code=503, detail="Queue not initialised")
    depth = await queue.queue_depth()
    metrics.set_gauge("queue_depth", depth)
    return {"queue_depth": depth}


@app.get("/v1/queue/dlq")
async def dlq_messages_endpoint(count: int = 20):
    if not queue:
        raise HTTPException(status_code=503, detail="Queue not initialised")
    if hasattr(queue, "dlq_messages"):
        messages = await queue.dlq_messages(count)
        return {"dlq_messages": messages, "count": len(messages)}
    return {"dlq_messages": [], "count": 0, "note": "DLQ inspection not supported by current queue backend"}


@app.post("/v1/queue/dlq/{entry_id}/retry")
async def retry_dlq_message_endpoint(entry_id: str):
    if not queue:
        raise HTTPException(status_code=503, detail="Queue not initialised")
    if hasattr(queue, "retry_dlq_message"):
        new_id = await queue.retry_dlq_message(entry_id)
        if new_id:
            return {"status": "retried", "new_stream_id": new_id}
        raise HTTPException(status_code=404, detail="DLQ entry not found")
    raise HTTPException(status_code=501, detail="DLQ retry not supported by current queue backend")


@app.get("/v1/notifications/recent")
async def recent_notifications(count: int = 20):
    """Return recent processed notifications from Redis (if available)."""
    if not queue:
        raise HTTPException(status_code=503, detail="Queue not initialised")
    try:
        import redis.asyncio as aioredis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = aioredis.from_url(redis_url, decode_responses=True)
        raw = await r.lrange("notifii:recent_notifications", 0, count - 1)
        await r.aclose()
        notifications = [json.loads(item) for item in raw]
        return {"notifications": notifications, "count": len(notifications)}
    except Exception:
        return {"notifications": [], "count": 0, "note": "Recent notifications unavailable"}


# ---------------------------------------------------------------------------
# Failure simulation (interview demo endpoints)
# ---------------------------------------------------------------------------
@app.post("/internal/simulate/provider-failure")
async def simulate_provider_failure(enable: bool = True):
    global _simulate_provider_failure
    _simulate_provider_failure = enable
    log.info("simulation_toggled", simulation="provider_failure", enabled=enable)
    return {"simulation": "provider_failure", "enabled": enable}


@app.post("/internal/simulate/slow-delivery")
async def simulate_slow_delivery(enable: bool = True):
    global _simulate_slow_delivery
    _simulate_slow_delivery = enable
    log.info("simulation_toggled", simulation="slow_delivery", enabled=enable)
    return {"simulation": "slow_delivery", "enabled": enable}


@app.get("/internal/config")
async def internal_config():
    return {
        "queue_backend": os.getenv("QUEUE_BACKEND", "redis"),
        "email_provider": os.getenv("EMAIL_PROVIDER", "console"),
        "idempotency_backend": os.getenv("IDEMPOTENCY_BACKEND", "redis"),
        "demo_mode": DEMO_MODE,
        "simulate_provider_failure": _simulate_provider_failure,
        "simulate_slow_delivery": _simulate_slow_delivery,
    }


# ---------------------------------------------------------------------------
# Demo endpoints (recruiter-friendly interactive demo)
# ---------------------------------------------------------------------------
DEMO_SEED_DATA = [
    {"channel": "email", "recipient": "alice@example.com", "message": "Your order #1042 has been shipped!"},
    {"channel": "email", "recipient": "bob@example.com", "message": "Password reset requested for your account."},
    {"channel": "email", "recipient": "carol@example.com", "message": "Welcome to Notifii! Your account is ready."},
    {"channel": "email", "recipient": "dave@example.com", "message": "Payment of $49.99 processed successfully."},
    {"channel": "email", "recipient": "eve@example.com", "message": "New login detected from San Francisco, CA."},
]

_demo_activity: list[dict] = []


@app.post("/demo/seed")
async def demo_seed():
    """Seed the queue with example notifications to demonstrate the pipeline."""
    if not queue:
        raise HTTPException(status_code=503, detail="Queue not initialised")

    seeded = []
    for item in DEMO_SEED_DATA:
        message_id = str(uuid4())
        payload = inject_trace_context({
            "message_id": message_id,
            "request_id": f"demo-seed-{message_id[:8]}",
            "channel": item["channel"],
            "recipient": item["recipient"],
            "message": item["message"],
            "idempotency_key": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "simulate_failure": False,
            "simulate_slow": False,
        })
        await queue.send(payload, attributes={"channel": item["channel"]})
        metrics.inc("notifications_received_total")
        metrics.inc("notifications_queued_total")
        seeded.append({"message_id": message_id, "recipient": item["recipient"]})
        _demo_activity.append({
            "action": "seed",
            "message_id": message_id,
            "recipient": item["recipient"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    log.info("demo_seeded", count=len(seeded))
    return {"status": "seeded", "count": len(seeded), "messages": seeded}


@app.post("/demo/send-test")
async def demo_send_test(
    recipient: str = "demo@example.com",
    message: str = "Test notification from Notifii playground!",
):
    """Quick single-notification send for the demo playground."""
    if not queue:
        raise HTTPException(status_code=503, detail="Queue not initialised")

    message_id = str(uuid4())
    payload = inject_trace_context({
        "message_id": message_id,
        "request_id": f"demo-test-{message_id[:8]}",
        "channel": "email",
        "recipient": recipient,
        "message": message,
        "idempotency_key": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "simulate_failure": _simulate_provider_failure,
        "simulate_slow": _simulate_slow_delivery,
    })
    await queue.send(payload, attributes={"channel": "email"})
    metrics.inc("notifications_received_total")
    metrics.inc("notifications_queued_total")

    _demo_activity.append({
        "action": "send_test",
        "message_id": message_id,
        "recipient": recipient,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    log.info("demo_send_test", message_id=message_id, recipient=recipient)
    return {"message_id": message_id, "status": "queued", "recipient": recipient}


@app.get("/demo/activity")
async def demo_activity(limit: int = 50):
    """Return recent demo activity log for the playground UI."""
    return {"activity": _demo_activity[-limit:], "count": len(_demo_activity[-limit:])}
