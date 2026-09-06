"""Unit tests for declarative DI injection in controller handlers."""

import json
from typing import Annotated, Any, cast

from django.http import HttpRequest

from do_as_beginner.http.base import require_GET, require_POST
from do_as_beginner.server.di import DIContainer, NamedDependency, set_default_container


class _FakeRequest:
    def __init__(self, method: str) -> None:
        self.method = method
        self.path = "/fake/"


class _Repo:
    pass


class _Svc:
    pass


def _install(container: DIContainer) -> None:
    set_default_container(container)


def _call(handler: object) -> Any:
    """Invoke a decorated handler as an untyped callable (DI fills the gaps)."""

    return cast("Any", handler)


async def test_async_handler_gets_type_first_injected_params() -> None:
    container = DIContainer()
    repo = _Repo()
    container.register(repo, key="repo")
    _install(container)

    class Controller:
        @require_GET
        async def items(self, request: HttpRequest, repo: _Repo) -> tuple[str, _Repo]:
            return "ok", repo

    result = await _call(Controller().items)(_FakeRequest("GET"))
    assert result == ("ok", repo)


async def test_async_handler_alias_marker_injection() -> None:
    container = DIContainer()
    first = _Repo()
    second = _Repo()
    container.register(first, key="repo_a")
    container.register(second, key="repo_b")
    _install(container)

    class Controller:
        @require_GET
        async def items(self, request: HttpRequest, repo: Annotated[_Repo, NamedDependency("repo_a")]) -> _Repo:
            return repo

    assert await _call(Controller().items)(_FakeRequest("GET")) is first


async def test_sync_handler_injection() -> None:
    container = DIContainer()
    repo = _Repo()
    container.register(repo, key="repo")
    _install(container)

    class Controller:
        @require_GET
        def items(self, request: HttpRequest, repo: _Repo) -> _Repo:
            return repo

    assert _call(Controller().items)(_FakeRequest("GET")) is repo


async def test_disallowed_method_returns_405_without_injection() -> None:
    container = DIContainer()
    container.register(_Repo(), key="repo")
    _install(container)

    class Controller:
        @require_GET
        async def items(self, request: HttpRequest, repo: _Repo) -> tuple[str, _Repo]:
            return "ok", repo

    response = await _call(Controller().items)(_FakeRequest("POST"))
    assert json.loads(response.content)["code"] == 405


async def test_non_di_params_are_left_untouched() -> None:
    container = DIContainer()
    container.register(_Svc(), key="svc")
    _install(container)

    class Controller:
        @require_POST
        async def create(
            self,
            request: HttpRequest,
            label: str,
            svc: _Svc,
        ) -> tuple[str, str, _Svc]:
            return label, "ok", svc

    result = await _call(Controller().create)(_FakeRequest("POST"), label="hello")
    assert result == ("hello", "ok", container.get(_Svc))
