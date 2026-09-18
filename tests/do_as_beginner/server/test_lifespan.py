"""Unit tests for the ASGI lifespan wrapper (plugin ``__lifespan__`` wiring)."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, contextmanager
from typing import Any

import pytest

from do_as_beginner.server.core import LifespanWrapper


class LifespanHarness:
    """Drive the wrapper's lifespan protocol with scripted receive/send."""

    def __init__(self, wrapper: LifespanWrapper) -> None:

        self.wrapper = wrapper
        self.sent: list[dict[str, Any]] = []
        self._messages: list[dict[str, Any]] = []

    def queue(self, *messages: dict[str, Any]) -> None:

        self._messages.extend(messages)

    async def receive(self) -> dict[str, Any]:

        return self._messages.pop(0)

    async def send(self, message: dict[str, Any]) -> None:

        self.sent.append(message)

    async def run(self, *messages: dict[str, Any]) -> None:

        self.queue(*messages)
        await self.wrapper({"type": "lifespan"}, self.receive, self.send)


@pytest.mark.asyncio
async def test_http_scope_is_proxied_untouched() -> None:

    captured: dict[str, Any] = {}

    async def inner(scope: dict[str, Any], receive: Callable[[], Any], send: Callable[..., Any]) -> None:

        captured["scope"] = scope

    wrapper = LifespanWrapper(inner, [])
    scope = {"type": "http", "path": "/"}

    await wrapper(scope, None, None)  # type: ignore[arg-type]

    assert captured["scope"] is scope


@pytest.mark.asyncio
async def test_lifespan_startup_and_shutdown_complete() -> None:

    events: list[str] = []

    @contextmanager
    def sync_resource() -> Any:

        events.append("sync.enter")
        yield
        events.append("sync.exit")

    @asynccontextmanager
    async def async_resource() -> AsyncIterator[str]:

        events.append("async.enter")
        yield "resource"
        events.append("async.exit")

    harness = LifespanHarness(LifespanWrapper(None, [sync_resource, async_resource]))  # type: ignore[arg-type]

    await harness.run({"type": "lifespan.startup"}, {"type": "lifespan.shutdown"})

    assert harness.sent == [
        {"type": "lifespan.startup.complete"},
        {"type": "lifespan.shutdown.complete"},
    ]
    # declaration order on startup, reverse on shutdown
    assert events == ["sync.enter", "async.enter", "async.exit", "sync.exit"]


class BrokenResource:
    """Context manager whose enter raises (startup failure)."""

    def __enter__(self) -> None:

        msg = "cannot start"
        raise RuntimeError(msg)

    def __exit__(self, *_args: object) -> None:

        return None


@pytest.mark.asyncio
async def test_startup_failure_reports_and_skips_shutdown() -> None:

    harness = LifespanHarness(LifespanWrapper(None, [BrokenResource]))  # type: ignore[arg-type]

    await harness.run({"type": "lifespan.startup"})

    assert harness.sent[0]["type"] == "lifespan.startup.failed"
    assert "cannot start" in harness.sent[0]["message"]


@pytest.mark.asyncio
async def test_shutdown_without_startup_only_completes() -> None:

    harness = LifespanHarness(LifespanWrapper(None, []))  # type: ignore[arg-type]

    await harness.run({"type": "lifespan.shutdown"})

    assert harness.sent == [{"type": "lifespan.shutdown.complete"}]
