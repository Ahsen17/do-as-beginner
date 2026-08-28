from collections.abc import Awaitable, Callable
from functools import wraps
from inspect import iscoroutinefunction, signature
from typing import TYPE_CHECKING, cast

from django.utils.log import log_response

from do_as_beginner.shared import GenericResponse

if TYPE_CHECKING:
    from django.http import HttpRequest


def require_http_methods[**P, R](
    request_method_list: list[str],
) -> Callable[
    [Callable[P, R] | Callable[P, Awaitable[R]]],
    Callable[P, R] | Callable[P, Awaitable[R]],
]:

    def decorator[**P, R](
        func: Callable[P, R] | Callable[P, Awaitable[R]],
    ) -> Callable[P, R] | Callable[P, Awaitable[R]]:

        func = func.__func__ if isinstance(func, (classmethod, staticmethod)) else func
        func_signature = signature(func)

        if iscoroutinefunction(func):

            @wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:

                request = cast(
                    "HttpRequest",
                    func_signature.bind_partial(*args, **kwargs).arguments.get("request"),
                )

                if request.method not in request_method_list:
                    response = GenericResponse(
                        code=405,
                        message="Method Not Allowed",
                    )
                    log_response(
                        "Method Not Allowed (%s): %s",
                        request.method,
                        request.path,
                        response=response,
                        request=request,
                    )
                    return response

                return await func(request, *args, **kwargs)

        else:

            @wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:

                request = cast(
                    "HttpRequest",
                    func_signature.bind_partial(*args, **kwargs).arguments.get("request"),
                )

                if request.method not in request_method_list:
                    response = GenericResponse(
                        code=405,
                        message="Method Not Allowed",
                    )
                    log_response(
                        "Method Not Allowed (%s): %s",
                        request.method,
                        request.path,
                        response=response,
                        request=request,
                    )
                    return response

                return func(request, *args, **kwargs)

        return wrapper

    return decorator
