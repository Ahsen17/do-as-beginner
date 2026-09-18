"""ASGI lifespan wrapper around Django's ASGIHandler.

Django's ``ASGIHandler`` does not handle the lifespan protocol (it raises on
non-HTTP scopes), so the framework wraps it: this wrapper serves
``lifespan.startup``/``lifespan.shutdown`` around the inner application and
proxies every other scope straight through.
"""

import traceback
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager, AbstractContextManager, AsyncExitStack
from typing import Any

__all__ = ("LifespanWrapper",)


class LifespanWrapper:
    """ASGI application serving the lifespan protocol around an inner app.

    Lifespan context managers (plugin-declared ``__lifespan__``) are entered
    in declaration order at startup and exited in reverse at shutdown.
    """

    def __init__(
        self,
        asgi_app: Callable[..., Any],
        lifespans: Sequence[Callable[[], AbstractContextManager[Any] | AbstractAsyncContextManager[Any]]],
    ) -> None:

        self._asgi_app = asgi_app
        self._lifespans = list(lifespans)
        self._stack: AsyncExitStack | None = None

    async def __call__(self, scope: dict[str, Any], receive: Callable[[], Any], send: Callable[..., Any]) -> None:

        if scope["type"] != "lifespan":
            await self._asgi_app(scope, receive, send)
            return

        started = False
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    await self._startup()
                except Exception:  # noqa: BLE001 -- the failure is reported to the server via startup.failed
                    await send({"type": "lifespan.startup.failed", "message": traceback.format_exc()})
                    break
                await send({"type": "lifespan.startup.complete"})
                started = True
            elif message["type"] == "lifespan.shutdown":
                if started:
                    await self._shutdown()
                await send({"type": "lifespan.shutdown.complete"})
                break
            else:
                # Unknown lifespan message types must not hang the loop; stop serving.
                break

    async def _startup(self) -> None:

        stack = AsyncExitStack()
        try:
            for factory in self._lifespans:
                context = factory()
                if isinstance(context, AbstractAsyncContextManager):
                    await stack.enter_async_context(context)
                else:
                    stack.enter_context(context)
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack

    async def _shutdown(self) -> None:

        stack, self._stack = self._stack, None
        if stack is not None:
            await stack.aclose()
