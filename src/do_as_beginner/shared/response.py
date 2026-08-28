import json
from typing import Annotated, Any

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from pydantic import BeforeValidator

__all__ = ("GenericResponse",)


def is_serializable(value: Any) -> Any:
    """Check if the value is serializable."""

    if value is None:
        return value

    try:
        json.dumps(value)

    except json.JSONDecodeError as exc:
        raise ValueError("Value is not serializable") from exc

    return value


class GenericResponse(HttpResponse):
    """Generic class for handling responses."""

    def __init__(
        self,
        code: int,
        message: str,
        data: Annotated[Any | None, BeforeValidator(is_serializable)] = None,
        **kwargs: Any,
    ) -> None:

        kwargs.setdefault("content_type", "application/json")
        super().__init__(
            content=json.dumps(
                {
                    "code": code,
                    "message": message,
                    "data": data,
                },
                cls=DjangoJSONEncoder,
            ),
            **kwargs,
        )
