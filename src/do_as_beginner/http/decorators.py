from collections.abc import Callable
from functools import wraps
from inspect import iscoroutinefunction, signature
from typing import TYPE_CHECKING, Any, TypeVar, cast

from django.utils.log import log_response

from do_as_beginner.shared import GenericResponse

if TYPE_CHECKING:
    from django.http import HttpRequest

__all__ = ("require_http_methods",)

T = TypeVar("T", bound=Callable[..., Any])


def _method_not_allowed(request: "HttpRequest | None") -> GenericResponse:
    """Build the 405 response for a disallowed request method."""

    response = GenericResponse(code=405, message="Method Not Allowed")
    if request is not None:
        log_response(
            "Method Not Allowed (%s): %s",
            request.method,
            request.path,
            response=response,
            request=request,
        )

    return response


def require_http_methods(request_method_list: list[str]) -> Callable[[T], T]:
    """Restrict a view function to the given HTTP methods.

    Works for both synchronous and asynchronous callables. When the request
    method is not in ``request_method_list``, a 405 :class:`GenericResponse`
    is returned.
    """

    def decorator(func: T) -> T:

        unwrapped = cast("Any", func).__func__ if isinstance(func, (classmethod, staticmethod)) else func
        func_signature = signature(cast("Callable[..., Any]", unwrapped))

        if iscoroutinefunction(unwrapped):

            @wraps(cast("Callable[..., Any]", unwrapped))
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:

                request = cast(
                    "HttpRequest | None",
                    func_signature.bind_partial(*args, **kwargs).arguments.get("request"),
                )

                if request is None or request.method not in request_method_list:
                    return _method_not_allowed(request)

                return await cast("Callable[..., Any]", unwrapped)(*args, **kwargs)

            return cast("T", async_wrapper)

        @wraps(cast("Callable[..., Any]", unwrapped))
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:

            request = cast(
                "HttpRequest | None",
                func_signature.bind_partial(*args, **kwargs).arguments.get("request"),
            )

            if request is None or request.method not in request_method_list:
                return _method_not_allowed(request)

            return cast("Callable[..., Any]", unwrapped)(*args, **kwargs)

        return cast("T", sync_wrapper)

    return decorator
