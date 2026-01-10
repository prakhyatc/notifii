# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from openapi_server.models.error_response import ErrorResponse
from openapi_server.models.health_response import HealthResponse
from openapi_server.models.ready_response import ReadyResponse


class BaseHealthApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseHealthApi.subclasses = BaseHealthApi.subclasses + (cls,)
    async def get_health(
        self,
    ) -> HealthResponse:
        """Returns 200 if the service process is running."""
        ...


    async def get_ready(
        self,
    ) -> ReadyResponse:
        """Returns 200 when the service is ready to accept traffic."""
        ...
