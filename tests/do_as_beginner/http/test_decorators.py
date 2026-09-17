"""Unit tests for declarative DI injection in controller handlers."""

import json
from typing import Annotated, Any, cast

from django.http import HttpRequest

from do_as_beginner.http.base import require_GET, require_POST
from do_as_beginner.server.depi import Container, NamedDependency


class _FakeRequest:
    def __init__(self, method: str) -> None:
        self.method = method
        self.path = "/fake/"


class _Repo:
    pass


class _Svc:
    pass


def _call(handler: object) -> Any:
    """Invoke a decorated handler as an untyped callable (DI fills the gaps)."""

    return cast("Any", handler)


async def test_async_handler_gets_type_first_injected_params(default_container: Container) -> None:
    repo = _Repo()
    default_container.register(repo, key="repo")

    class Controller:
        @require_GET
        async def items(self, request: HttpRequest, repo: _Repo) -> tuple[str, _Repo]:
            return "ok", repo

    result = await _call(Controller().items)(_FakeRequest("GET"))
    assert result == ("ok", repo)


async def test_async_handler_alias_marker_injection(default_container: Container) -> None:
    first = _Repo()
    second = _Repo()
    default_container.register(first, key="repo_a")
    default_container.register(second, key="repo_b")

    class Controller:
        @require_GET
        async def items(self, request: HttpRequest, repo: Annotated[_Repo, NamedDependency(key="repo_a")]) -> _Repo:
            return repo

    assert await _call(Controller().items)(_FakeRequest("GET")) is first


async def test_sync_handler_injection(default_container: Container) -> None:
    repo = _Repo()
    default_container.register(repo, key="repo")

    class Controller:
        @require_GET
        def items(self, request: HttpRequest, repo: _Repo) -> _Repo:
            return repo

    assert _call(Controller().items)(_FakeRequest("GET")) is repo


async def test_disallowed_method_returns_405_without_injection(default_container: Container) -> None:
    default_container.register(_Repo(), key="repo")

    class Controller:
        @require_GET
        async def items(self, request: HttpRequest, repo: _Repo) -> tuple[str, _Repo]:
            return "ok", repo

    response = await _call(Controller().items)(_FakeRequest("POST"))
    assert json.loads(response.content)["code"] == 405


async def test_non_di_params_are_left_untouched(default_container: Container) -> None:
    default_container.register(_Svc(), key="svc")

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
    assert result == ("hello", "ok", default_container.get(_Svc))
