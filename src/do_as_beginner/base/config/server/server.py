from typing import Literal

from pydantic import Field

from do_as_beginner.base.config.constants import APP_NAME
from do_as_beginner.base.schemas import BaseStruct

from .master import MasterConfig

__all__ = ("ServerConfig",)


class ServerConfig(BaseStruct):
    """Server configuration class."""

    name: str = APP_NAME
    host: str = "localhost"
    port: int = 8080
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    workers: int = 1
    master: MasterConfig = Field(default_factory=MasterConfig)
