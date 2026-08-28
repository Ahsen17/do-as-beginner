from typing import Any

from django.http import HttpRequest
from django.urls import path
from django.urls.resolvers import URLResolver

from do_as_beginner.http.base import BaseController, require_GET, require_POST
from do_as_beginner.shared import GenericResponse

__all__ = ("SystemController",)


class SystemController(BaseController):
    """System Controller Class"""

    path = "system"
    name = "System Controller"

    @require_POST
    async def health(
        self,
        request: HttpRequest,
        extra_context: Any = None,
    ) -> GenericResponse:

        return GenericResponse(code=200, message="ok")

    def get_urls(self) -> list[URLResolver]:

        return [
            path("health/", self.health, name="System health"),
        ]

    @property
    def urls(self) -> tuple[URLResolver, str, str]:
        return self.get_urls(), "system", self.name
