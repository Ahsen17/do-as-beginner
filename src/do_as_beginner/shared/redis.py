from typing import TYPE_CHECKING

from redis.asyncio import Redis
from redis.asyncio.connection import BlockingConnectionPool

if TYPE_CHECKING:
    from do_as_beginner.base import RedisConfig

__all__ = ("RedisFactory",)


class RedisFactory:
    """Factory for async redis"""

    def __init__(self, config: "RedisConfig") -> None:

        self._config = config

        self._conn_pool: BlockingConnectionPool | None = None

        if self._config.pool_enabled:
            self._conn_pool = BlockingConnectionPool.from_url(
                url=self._config.dsn,
                max_connections=self._config.pool_size,
                timeout=self._config.connection_timeout,
            )

    def create(self) -> Redis:

        if self._config.pool_enabled and self._conn_pool is not None:
            return Redis(connection_pool=self._conn_pool)

        return Redis.from_url(url=self._config.dsn)
