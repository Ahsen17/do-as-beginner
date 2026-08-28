# ruff: noqa: N816
# flake8: noqa: N816

from typing import ClassVar

from django.urls.resolvers import URLPattern, URLResolver

from .decorators import require_http_methods

__all__ = ("BaseController",)


require_GET = require_http_methods(["GET"])
require_POST = require_http_methods(["POST"])
require_PUT = require_http_methods(["PUT"])
require_DELETE = require_http_methods(["DELETE"])
require_PATCH = require_http_methods(["PATCH"])
require_HEAD = require_http_methods(["HEAD"])
require_OPTIONS = require_http_methods(["OPTIONS"])


class BaseController:
    """Base controller class for handling URLs."""

    path: ClassVar[str]
    name: ClassVar[str]

    def get_urls(self) -> list[URLResolver | URLPattern]:

        raise NotImplementedError("Subclasses must implement the get_urls method.")

    @property
    def urls(self) -> tuple[URLResolver | URLPattern, str, str]:

        raise NotImplementedError("Subclasses must implement the url property.")
