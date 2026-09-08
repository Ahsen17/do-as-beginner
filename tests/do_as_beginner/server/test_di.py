"""Unit tests for the lightweight DI container (``server.di``)."""

from typing import Annotated

import pytest

from do_as_beginner.server.di import (
    AmbiguousDependencyError,
    AsyncDependencyError,
    CircularDependencyError,
    DependencyNotFoundError,
    DIContainer,
    DuplicateDependencyError,
    NamedDependency,
    get_default_container,
    set_default_container,
)


class _Redis:
    pass


class _Db:
    def __init__(self, name: str = "default") -> None:
        self.name = name


class _Svc:
    def __init__(self, db: _Db) -> None:
        self.db = db


def test_register_value_supports_key_and_type_lookup() -> None:
    container = DIContainer()
    redis = _Redis()
    container.register(redis, key="redis_a")

    assert container.get("redis_a") is redis
    assert container.get(_Redis) is redis


def test_register_duplicate_key_raises() -> None:
    container = DIContainer()
    container.register(_Redis(), key="redis")

    with pytest.raises(DuplicateDependencyError):
        container.register(_Redis(), key="redis")


def test_register_class_resolves_constructor_from_container() -> None:
    container = DIContainer()
    db = _Db()
    container.register(db, key="db")
    container.register(_Svc)

    assert container.get(_Svc).db is db


def test_register_factory_uses_return_annotation_as_type() -> None:
    container = DIContainer()

    def build_db() -> _Db:
        return _Db(name="built")

    container.register(build_db, key="build_db")

    assert isinstance(container.get("build_db"), _Db)
    assert container.get(_Db).name == "built"


def test_singleton_semantics_return_same_instance() -> None:
    container = DIContainer()
    container.register(_Db(), key="db")
    container.register(_Svc)

    assert container.get(_Svc) is container.get(_Svc)


def test_ambiguous_type_requires_alias() -> None:
    container = DIContainer()
    first = _Redis()
    second = _Redis()
    container.register(first, key="redis_a")
    container.register(second, key="redis_b")

    with pytest.raises(AmbiguousDependencyError):
        container.get(_Redis)

    assert container.get("redis_b") is second  # key lookup still works
    assert container.get("redis_a") is first


def test_alias_marker_disambiguates_consumer_params() -> None:
    container = DIContainer()
    first = _Redis()
    second = _Redis()
    container.register(first, key="redis_a")
    container.register(second, key="redis_b")

    def consume(redis: Annotated[_Redis, NamedDependency("redis_a")]) -> _Redis:
        return redis

    assert container.inject(consume) == {"redis": first}


def test_implicit_type_first_consumer_injection() -> None:
    container = DIContainer()
    db = _Db()
    container.register(db, key="db")

    def consume(connection: _Db, label: str = "x") -> tuple[_Db, str]:
        return connection, label

    injected = container.inject(consume)
    assert injected == {"connection": db}  # `label` has a default and is not a registered type


def test_unregistered_key_raises() -> None:
    container = DIContainer()

    with pytest.raises(DependencyNotFoundError):
        container.get("nope")


def test_nested_dependency_resolves_in_topological_order() -> None:
    container = DIContainer()
    order: list[str] = []

    def build_db() -> _Db:
        order.append("db")
        return _Db()

    def build_svc(db: _Db) -> _Svc:
        order.append("svc")
        return _Svc(db)

    container.register(build_db, key="db")
    container.register(build_svc, key="svc")

    svc: _Svc = container.get("svc")
    assert isinstance(svc.db, _Db)
    assert order == ["db", "svc"]


def test_circular_dependency_raises() -> None:
    container = DIContainer()

    def a(b: Annotated[_Redis, NamedDependency("b")]) -> _Db:
        return _Db()

    def b(a: Annotated[_Db, NamedDependency("a")]) -> _Redis:
        return _Redis()

    container.register(a, key="a")
    container.register(b, key="b")

    with pytest.raises(CircularDependencyError):
        container.get("a")


async def test_async_provider_resolves_via_aget() -> None:
    container = DIContainer()

    async def build_redis() -> _Redis:
        return _Redis()

    container.register(build_redis, key="async_redis")

    assert isinstance(await container.aget("async_redis"), _Redis)


def test_sync_get_on_async_provider_raises() -> None:
    container = DIContainer()

    async def build_redis() -> _Redis:
        return _Redis()

    container.register(build_redis, key="async_redis")

    with pytest.raises(AsyncDependencyError):
        container.get("async_redis")


async def test_sync_get_returns_cached_async_value() -> None:
    container = DIContainer()

    async def build_redis() -> _Redis:
        return _Redis()

    container.register(build_redis, key="async_redis")

    value: _Redis = await container.aget("async_redis")
    assert container.get("async_redis") is value  # cached singleton, sync path fine


async def test_ainject_resolves_async_and_sync_dependencies() -> None:
    container = DIContainer()
    db = _Db()
    container.register(db, key="db")

    async def build_redis() -> _Redis:
        return _Redis()

    container.register(build_redis, key="redis")

    async def consume(connection: _Db, redis: _Redis) -> tuple[_Db, _Redis]:
        return connection, redis

    injected = await container.ainject(consume)
    assert injected["connection"] is db
    assert isinstance(injected["redis"], _Redis)


def test_default_container_is_process_wide_singleton() -> None:
    first = get_default_container()
    second = get_default_container()
    assert first is second


def test_set_default_container_overrides() -> None:
    fresh = DIContainer()
    set_default_container(fresh)
    try:
        assert get_default_container() is fresh
    finally:
        set_default_container(DIContainer())  # restore for other tests
