from do_as_beginner.base.schemas import BaseStruct

__all__ = ("RedisConfig",)


class RedisConfig(BaseStruct):
    """Configuration for redis"""

    dsn: str = "redis://localhost:6379/0"

    pool_enabled: bool = False
    pool_size: int = 50
    connection_timeout: float = 20.0
