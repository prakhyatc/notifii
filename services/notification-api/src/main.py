from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from fastapi import FastAPI, Header, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

APP_ENV = os.getenv("APP_ENV", "dev")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
QUEUE_URL = os.getenv("NOTIFII_QUEUE_URL")

sqs = boto3.client("sqs", region_name=AWS_REGION)
# ----------------------------
# Logging (structured JSON)
# ----------------------------
logger = logging.getLogger("notifii.notification_api")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.handlers = [handler]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_json(level: str, event: str, **fields: Any) -> None:
    payload = {
        "timestamp": utc_now_iso(),
        "level": level,
        "service": "notification-api",
        "env": APP_ENV,
        "event": event,
        **fields,
    }
    line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    if level == "ERROR":
        logger.error(line)
    else:
        logger.info(line)


# ----------------------------
# API Schemas (Pydantic)
# ----------------------------
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


# ----------------------------
# App
# ----------------------------
app = FastAPI(
    title="Notifii Notification API",
    version="1.0.0",
)


# ----------------------------
# Global error handling
# ----------------------------
@app.exception_handler(ValidationError)
async def pydantic_validation_error_handler(request: Request, exc: ValidationError):
    details = []
    for err in exc.errors():
        # err["loc"] can be like ("body", "channel")
        loc = err.get("loc", [])
        field = None
        if isinstance(loc, (list, tuple)) and len(loc) >= 2:
            field = str(loc[-1])
        details.append(ErrorDetail(field=field, issue=err.get("msg", "Invalid value")))

    trace_id = request.headers.get("x-request-id")
    body = ErrorResponse(
        error=ErrorObject(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details=details,
        )
    ).model_dump()

    log_json(
        "ERROR",
        "validation_error",
        trace_id=trace_id,
        path=str(request.url.path),
        method=request.method,
        detail_count=len(details),
    )
    return JSONResponse(status_code=400, content=body)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    trace_id = request.headers.get("x-request-id")
    body = ErrorResponse(
        error=ErrorObject(
            code="INTERNAL_ERROR",
            message="Unexpected error occurred",
        )
    ).model_dump()

    log_json(
        "ERROR",
        "unhandled_exception",
        trace_id=trace_id,
        path=str(request.url.path),
        method=request.method,
        exception_type=type(exc).__name__,
    )
    return JSONResponse(status_code=500, content=body)


# ----------------------------
# Health endpoints
# ----------------------------
@app.get("/health")
async def health() -> Dict[str, str]:
    # Liveness: if process is up, it's OK
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> Dict[str, str]:
    # Readiness: check dependencies (DB, queue, etc.)
    # Week 1–2: same as health
    return {"status": "ready"}


# ----------------------------
# Core endpoint: enqueue notification
# ----------------------------
@app.post("/v1/notifications:send", status_code=202)
async def send_notification(
    payload: SendNotificationRequest,
    request: Request,
    x_request_id: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    # Trace ID: prefer header if present, otherwise create one for logs
    trace_id = x_request_id or str(uuid4())
    if not QUEUE_URL:
        raise HTTPException(
            status_code=500,
            detail="NOTIFII_QUEUE_URL is not configured",
        )


    message_id = str(uuid4())
    request_id = trace_id

    # Placeholder enqueue (Week 1–2): simulate async queue publish
    # Later: publish to SQS (and store idempotency mapping if idempotency_key provided)
    sqs_payload = {
        "message_id": message_id,
        "request_id": request_id,
        "channel": payload.channel,
        "recipient": payload.recipient,
        "message": payload.message,
        "idempotency_key": payload.idempotency_key,
        "timestamp": utc_now_iso(),
    }

    try:
        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(sqs_payload),
            MessageAttributes={
                "channel": {
                    "DataType": "String",
                    "StringValue": payload.channel,
                }
            },
        )
    except (BotoCoreError, ClientError) as e:
        log_json(
            "ERROR",
            "sqs_send_failed",
            trace_id=trace_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to enqueue notification",
        )

    log_json(
        "INFO",
        "notification_queued",
        trace_id=trace_id,
        message_id=message_id,
        channel=payload.channel,
        has_idempotency_key=bool(payload.idempotency_key),
        path=str(request.url.path),
        method=request.method,
    )

    return SendNotificationResponse(
        message_id=message_id,
        status="queued",
    ).model_dump()
