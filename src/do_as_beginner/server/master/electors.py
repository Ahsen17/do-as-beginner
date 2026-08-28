from typing import Any

import structlog
from django_async_backend.db import async_connections

from .protocol import ElectorProtocol

__all__ = ("PostgresElector",)

logger = structlog.stdlib.get_logger(__name__)


class PostgresElector(ElectorProtocol):
    """Master elector imp based on postgresql."""

    def __init__(
        self,
        *,
        pid: int,
        lock_id: int,
        db_alias: str = "default",
    ) -> None:

        self._pid = pid
        self._lock_id = lock_id
        self._db_alias = db_alias

        self._conn: Any = None
        self._acquired = False

    @property
    def acquired(self) -> bool:

        return self._acquired

    async def acquire(self) -> bool:

        if self._conn is not None:
            raise RuntimeError("Master elector already owns a connection")

        conn = async_connections.create_connection(self._db_alias)
        self._conn = conn

        try:
            async with await conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT pg_try_advisory_lock(%s)",
                    [self._lock_id],
                )

                row = await cursor.fetchone()

            self._acquired = bool(row and row[0])

            if not self._acquired:
                await self._close_conn()

            return self._acquired

        except BaseException:
            logger.error(
                "Master try to acquire advisory lock failed, unknown error",
                pid=self._pid,
            )

            await self._close_conn()
            raise

    async def healthcheck(self) -> bool:

        if not self._acquired or self._conn is None:
            logger.error(
                "Current worker is not Master",
                pid=self._pid,
            )
            raise RuntimeError("Current worker is not Master")

        async with await self._conn.cursor() as cursor:
            await cursor.execute("SELECT 1")
            await cursor.fetchone()

    async def release(self) -> None:

        conn = self._conn
        if conn is None:
            return

        try:
            if self._acquired:
                async with await conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT pg_advisory_unlock(%s)",
                        [self._lock_id],
                    )

                row = await cursor.fetchone()

                if not row or not row[0]:
                    logger.warning(
                        "PostgreSQL advisory lock was not owned",
                        pid=self._pid,
                    )

        finally:
            self._acquired = False
            await self._close_conn()

    async def _close_conn(self) -> None:

        conn = self._conn
        self._conn = None

        if conn is not None:
            await conn.close()


# TODO: elector implementation based on redis

# class RedisElector(ElectorProtocol):
#     """Master elector imp based on redis."""
