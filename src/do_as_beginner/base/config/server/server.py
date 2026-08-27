from typing import Literal

from do_as_beginner.base.schemas import BaseStruct

__all__ = ("ServerConfig",)


class ServerConfig(BaseStruct):
    """Server configuration class."""

    host: str = "localhost"
    port: int = 8080
    debug: bool = False

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
