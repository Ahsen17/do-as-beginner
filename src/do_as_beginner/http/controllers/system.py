from typing import Any

from django.http import HttpRequest
from django.urls import path
from django.urls.resolvers import URLPattern, URLResolver
from opentelemetry import metrics, trace
from opentelemetry.trace import SpanKind

from do_as_beginner.http.base import BaseController, require_GET
from do_as_beginner.shared import GenericResponse

__all__ = ("SystemController",)


tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)


request_counter = meter.create_counter(
    name="system_health_request_counter",
    unit="requests",
    description="Counter for system health requests",
)


class SystemController(BaseController):
    """System Controller Class"""

    path = "system/"
    name = "System Controller"

    @require_GET
    async def health(
        self,
        request: HttpRequest,
        extra_context: Any = None,
    ) -> GenericResponse:

        with tracer.start_as_current_span(
            name="system.health",
            kind=SpanKind.SERVER,
        ) as span:
            span.attribute("system.health", "ok")

            request_counter.add(
                1,
                {
                    "operation": "acquire system health",
                    "result": "ok",
                },
            )

            return GenericResponse(code=200, message="ok")

    def get_urls(self) -> list[URLResolver | URLPattern]:

        return [
            path("health/", self.health, name="System health"),
        ]

    @property
    def urls(self) -> tuple[list[URLResolver | URLPattern], str, str]:
        return self.get_urls(), "system", self.name
