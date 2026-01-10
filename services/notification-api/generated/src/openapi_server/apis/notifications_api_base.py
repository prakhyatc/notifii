# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from openapi_server.models.error_response import ErrorResponse
from openapi_server.models.send_notification_request import SendNotificationRequest
from openapi_server.models.send_notification_response import SendNotificationResponse


class BaseNotificationsApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseNotificationsApi.subclasses = BaseNotificationsApi.subclasses + (cls,)
    async def send_notification(
        self,
        send_notification_request: SendNotificationRequest,
    ) -> SendNotificationResponse:
        """Accepts a notification request and enqueues it for asynchronous processing by the appropriate channel microservice. """
        ...
