import contextlib
from collections.abc import Awaitable, Callable

import anyio
import structlog

from .protocol import ElectorProtocol

__all__ = ("MasterCoordinator",)


AsyncCallback = Callable[[], Awaitable[None]]

logger = structlog.stdlib.get_logger(__name__)


class MasterCoordinator:
    """Master manage coordinator"""

    def __init__(
        self,
        *,
        pid: int,
        elector: ElectorProtocol,
        on_started: AsyncCallback,
        on_stopped: AsyncCallback,
        poll_interval: float = 5.0,
        healthcheck_interval: float = 5.0,
    ) -> None:

        self._pid = pid
        self._elector = elector
        self._on_started = on_started
        self._on_stopped = on_stopped
        self._poll_interval = poll_interval
        self._healthcheck_interval = healthcheck_interval

        self._stop_event = anyio.Event()
        self._is_master = False

    @property
    def is_master(self) -> bool:

        return self._is_master

    async def run(self) -> None:

        try:
            while not self._stop_event.is_set():
                try:
                    acquired = await self._elector.acquire()

                    if not acquired:
                        await self._wait(self._poll_interval)
                        continue

                    self._is_master = True
                    logger.info(
                        "Current worker became Master",
                        pid=self._pid,
                    )

                    await self._on_started()
                    await self._maintain()

                except anyio.get_cancelled_exc_class():
                    raise

                except Exception:
                    logger.exception(
                        "Master election cycle failed",
                        pid=self._pid,
                    )

                finally:
                    await self._leave()

                await self._wait(self._poll_interval)

        finally:
            await self._leave()

    async def stop(self) -> None:

        self._stop_event.set()

    async def _maintain(self) -> None:

        while not self._stop_event.is_set():
            await self._wait(self._poll_interval)

            if not self._stop_event.is_set():
                await self._elector.healthcheck()

    async def _leave(self) -> None:

        if self._is_master:
            self._is_master = False

            with contextlib.suppress(Exception):
                await self._on_stopped()

        with contextlib.suppress(Exception):
            await self._elector.release()

    async def _wait(self, timeout: float) -> None:

        with (
            contextlib.suppress(TimeoutError),
            anyio.move_on_after(timeout),
        ):
            await self._stop_event.wait()
