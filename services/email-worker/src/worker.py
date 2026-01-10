import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(event: str, **fields: Any) -> None:
    payload = {
        "ts": utc_now(),
        "service": os.getenv("SERVICE_NAME", "email-worker"),
        "env": os.getenv("APP_ENV", "dev"),
        "event": event,
        **fields,
    }
    print(json.dumps(payload, separators=(",", ":")), flush=True)


class ShutdownFlag:
    stopped = False


def _handle_shutdown(signum, frame):  # noqa: ARG001
    ShutdownFlag.stopped = True
    log("shutdown_signal_received", signum=signum)


def process_message(body: Dict[str, Any]) -> None:
    """
    Week 3 placeholder:
    - pretend to send email
    - validate required fields exist
    """
    required = ["message_id", "request_id", "channel", "recipient", "message"]
    missing = [k for k in required if k not in body]
    if missing:
        raise ValueError(f"missing_fields={missing}")

    if body["channel"] != "email":
        # For now this worker only handles email messages.
        # In a multi-worker setup, you can route by channel or use separate queues.
        raise ValueError(f"unexpected_channel={body['channel']}")

    log(
        "email_send_simulated",
        message_id=body["message_id"],
        request_id=body["request_id"],
        recipient=body["recipient"],
        idempotency_key=body.get("idempotency_key"),
    )


def main() -> int:
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    region = os.getenv("AWS_REGION", "us-east-1")
    queue_url = os.getenv("NOTIFII_QUEUE_URL")
    if not queue_url:
        log("config_error", error="NOTIFII_QUEUE_URL not set")
        return 2

    sqs = boto3.client("sqs", region_name=region)

    poll_wait_seconds = int(os.getenv("POLL_WAIT_SECONDS", "20"))  # long-poll
    max_batch = int(os.getenv("MAX_BATCH", "10"))

    log("worker_started", region=region, queue_url=queue_url)

    while not ShutdownFlag.stopped:
        try:
            resp = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_batch,
                WaitTimeSeconds=poll_wait_seconds,
                MessageAttributeNames=["All"],
                AttributeNames=["All"],
            )
        except (BotoCoreError, ClientError) as e:
            log("sqs_receive_error", error=str(e))
            time.sleep(2)
            continue

        messages = resp.get("Messages", [])
        if not messages:
            continue

        for m in messages:
            if ShutdownFlag.stopped:
                break

            receipt_handle = m["ReceiptHandle"]
            raw_body = m.get("Body", "")
            try:
                body = json.loads(raw_body)
                process_message(body)
                time.sleep(1.0)

                # Delete only after successful processing
                sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
                log(
                    "message_deleted",
                    sqs_message_id=m.get("MessageId"),
                    message_id=body.get("message_id"),
                    request_id=body.get("request_id"),
                )
            except Exception as e:
                # Do not delete → message will be retried and can end up in DLQ
                log(
                    "message_processing_failed",
                    error=str(e),
                    sqs_message_id=m.get("MessageId"),
                    body_preview=raw_body[:500],
                )

    log("worker_stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
