from typing import ClassVar, Self

from pydantic import Field

from do_as_beginner.base.schemas import BaseStruct

from .cache import RedisConfig
from .celery import CeleryConfig
from .constants import BASE_DIR
from .database import PostgresConfig, QdrantConfig
from .otel import OtelConfig
from .server import ServerConfig

__all__ = ("AppConfig",)


class AppConfig(BaseStruct):
    """Application configuration class."""

    _instance: ClassVar[Self | None] = None

    server: ServerConfig = Field(default_factory=ServerConfig)

    redis: RedisConfig = Field(default_factory=RedisConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)

    celery: CeleryConfig = Field(default_factory=CeleryConfig)
    otel: OtelConfig = Field(default_factory=OtelConfig)

    @classmethod
    def load(cls, filename: str = "config.yaml") -> Self:
        """Load configuration from a file."""

        if cls._instance is not None:
            return cls._instance

        if not (filepath := BASE_DIR.joinpath(filename)).exists():
            cls._instance = cls()

            return cls._instance

        match filepath.suffix:
            case ".yaml" | ".yml":
                return cls.from_yaml(filepath.read_text())
            case ".toml":
                return cls.from_toml(filepath.read_text())
            case ".json":
                return cls.from_json(filepath.read_text())
            case _:
                raise ValueError(f"Unsupported configuration file format: {filepath.suffix}")
