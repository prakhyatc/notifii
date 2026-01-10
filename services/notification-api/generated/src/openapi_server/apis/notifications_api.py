# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from openapi_server.apis.notifications_api_base import BaseNotificationsApi
import openapi_server.impl

from fastapi import (  # noqa: F401
    APIRouter,
    Body,
    Cookie,
    Depends,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
    Security,
    status,
)

from openapi_server.models.extra_models import TokenModel  # noqa: F401
from openapi_server.models.error_response import ErrorResponse
from openapi_server.models.send_notification_request import SendNotificationRequest
from openapi_server.models.send_notification_response import SendNotificationResponse


router = APIRouter()

ns_pkg = openapi_server.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/v1/notifications:send",
    responses={
        202: {"model": SendNotificationResponse, "description": "Accepted and queued for delivery"},
        400: {"model": ErrorResponse, "description": "Validation error (malformed payload, missing fields, invalid enums)"},
        409: {"model": ErrorResponse, "description": "Idempotency conflict (request already processed with this idempotency key)"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded (reserved for future)"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    tags=["Notifications"],
    summary="Enqueue a notification request",
    response_model_by_alias=True,
)
async def send_notification(
    send_notification_request: SendNotificationRequest = Body(None, description=""),
) -> SendNotificationResponse:
    """Accepts a notification request and enqueues it for asynchronous processing by the appropriate channel microservice. """
    if not BaseNotificationsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseNotificationsApi.subclasses[0]().send_notification(send_notification_request)
