from http import HTTPStatus
from typing import Any, ClassVar

__all__ = ("ApplicationError",)


class ApplicationError(Exception):
    """Base exception for expected application errors."""

    code: ClassVar[str] = "application_error"
    status_code: ClassVar[HTTPStatus] = HTTPStatus.BAD_REQUEST
    default_message: ClassVar[str] = "Application request failed."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details or {}

        super().__init__(self.message)

    def as_dict(self) -> dict[str, Any]:
        error: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }

        if self.details:
            error["details"] = self.details

        return error
