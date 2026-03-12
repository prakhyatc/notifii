from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from typing import Any, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from services.shared.queue import QueueAdapter, QueueMessage, create_queue_adapter
from services.shared.email import EmailAdapter, EmailPayload, create_email_adapter
from services.shared.idempotency import IdempotencyStore, MessageStatus, create_idempotency_store
from services.shared.observability import (
    StructuredLogger,
    metrics,
    init_tracing,
    extract_trace_context,
    start_span,
)

log = StructuredLogger("email-worker")


class ShutdownFlag:
    stopped = False


def _handle_shutdown(signum, frame):
    ShutdownFlag.stopped = True
    log.info("shutdown_signal_received", signum=signum)


async def _store_recent(body: Dict[str, Any], status: str) -> None:
    """Push processed notification to Redis list for the dashboard."""
    try:
        import redis.asyncio as aioredis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = aioredis.from_url(redis_url, decode_responses=True)
        record = {
            "message_id": body.get("message_id"),
            "recipient": body.get("recipient"),
            "channel": body.get("channel"),
            "status": status,
            "processed_at": time.time(),
        }
        await r.lpush("notifii:recent_notifications", json.dumps(record, separators=(",", ":")))
        await r.ltrim("notifii:recent_notifications", 0, 99)
        await r.aclose()
    except Exception:
        pass


async def process_message(
    body: Dict[str, Any],
    email_adapter: EmailAdapter,
    idempotency_store: IdempotencyStore | None,
) -> None:
    required = ["message_id", "request_id", "channel", "recipient", "message"]
    missing = [k for k in required if k not in body]
    if missing:
        raise ValueError(f"missing_fields={missing}")

    if body["channel"] != "email":
        raise ValueError(f"unexpected_channel={body['channel']}")

    message_id = body["message_id"]
    idempotency_key = body.get("idempotency_key")

    parent_ctx = extract_trace_context(body)

    with start_span(
        "process_notification",
        kind="consumer",
        attributes={
            "messaging.message_id": message_id,
            "messaging.destination": "notifii:notifications",
            "notification.channel": body["channel"],
            "notification.recipient": body["recipient"],
        },
        parent_context=parent_ctx,
    ) as span:
        if idempotency_key and idempotency_store:
            await idempotency_store.update_status(idempotency_key, MessageStatus.PROCESSING)

        if body.get("simulate_failure"):
            span.set_attribute("notification.simulated_failure", True)
            span.record_exception(RuntimeError("Simulated provider failure (demo)"))
            raise RuntimeError("Simulated provider failure (demo)")

        if body.get("simulate_slow"):
            span.set_attribute("notification.simulated_slow", True)
            log.info("simulating_slow_delivery", message_id=message_id, delay_seconds=5)
            await asyncio.sleep(5)

        payload = EmailPayload(
            to=body["recipient"],
            subject=f"Notification {message_id[:8]}",
            body=body["message"],
            message_id=message_id,
        )

        with start_span(
            "email_delivery",
            kind="client",
            attributes={
                "email.to": body["recipient"],
                "email.provider": email_adapter.provider_name,
            },
        ) as delivery_span:
            result = await email_adapter.send(payload)
            delivery_span.set_attribute("email.success", result.success)
            if result.provider_message_id:
                delivery_span.set_attribute("email.provider_message_id", result.provider_message_id)

        metrics.inc("notifications_processed_total")

        if result.success:
            metrics.inc("delivery_success_total")
            span.set_attribute("notification.status", "delivered")
            log.info(
                "email_delivered",
                message_id=message_id,
                request_id=body["request_id"],
                recipient=body["recipient"],
                provider=result.provider,
                provider_message_id=result.provider_message_id,
            )
            if idempotency_key and idempotency_store:
                await idempotency_store.update_status(idempotency_key, MessageStatus.DELIVERED)
            await _store_recent(body, "delivered")
        else:
            metrics.inc("delivery_failures_total")
            span.set_attribute("notification.status", "failed")
            span.record_exception(RuntimeError(result.error or "delivery failed"))
            log.error(
                "email_delivery_failed",
                message_id=message_id,
                request_id=body["request_id"],
                provider=result.provider,
                error=result.error,
            )
            if idempotency_key and idempotency_store:
                await idempotency_store.update_status(idempotency_key, MessageStatus.FAILED)
            await _store_recent(body, "failed")
            raise RuntimeError(f"Delivery failed via {result.provider}: {result.error}")


async def run() -> int:
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    init_tracing("notifii-worker")

    queue = create_queue_adapter()
    email_adapter = create_email_adapter()

    idempotency_store: IdempotencyStore | None = None
    try:
        idempotency_store = create_idempotency_store()
    except Exception as exc:
        log.warn("idempotency_store_unavailable", error=str(exc))

    poll_wait = int(os.getenv("POLL_WAIT_SECONDS", "5"))
    max_batch = int(os.getenv("MAX_BATCH", "10"))

    log.info(
        "worker_started",
        queue_backend=os.getenv("QUEUE_BACKEND", "redis"),
        email_provider=os.getenv("EMAIL_PROVIDER", "console"),
        poll_wait=poll_wait,
        max_batch=max_batch,
    )

    while not ShutdownFlag.stopped:
        try:
            messages = await queue.receive(max_messages=max_batch, wait_seconds=poll_wait)
        except Exception as exc:
            log.error("queue_receive_error", error=str(exc))
            await asyncio.sleep(2)
            continue

        if not messages:
            continue

        for msg in messages:
            if ShutdownFlag.stopped:
                break

            try:
                await process_message(msg.body, email_adapter, idempotency_store)
                await queue.delete(msg.receipt_handle)
                log.info(
                    "message_deleted",
                    message_id=msg.body.get("message_id"),
                    request_id=msg.body.get("request_id"),
                )
            except Exception as exc:
                log.error(
                    "message_processing_failed",
                    error=str(exc),
                    message_id=msg.body.get("message_id"),
                    body_preview=str(msg.body)[:500],
                )

    await queue.close()
    await email_adapter.close()
    if idempotency_store:
        await idempotency_store.close()

    log.info("worker_stopped")
    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
