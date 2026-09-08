"""Unit tests for plugin DI registration (Redis/Qdrant wire into the container)."""

from do_as_beginner.base import AppConfig
from do_as_beginner.server.di import DIContainer
from do_as_beginner.server.plugins import QdrantPlugin, RedisPlugin
from do_as_beginner.shared import RedisFactory


def test_redis_plugin_registers_singleton_into_container() -> None:
    container = DIContainer()
    config = AppConfig.load()

    RedisPlugin(config, container).setup()

    factory: RedisFactory = container.get("redis_factory")
    assert isinstance(factory, RedisFactory)
    # type-first lookup hits the same singleton
    assert container.get(RedisFactory) is factory


def test_qdrant_plugin_registers_into_container() -> None:
    container = DIContainer()
    config = AppConfig.load()

    QdrantPlugin(config, container).setup()

    assert "qdrant_client" in container._registrations
    assert container.get("qdrant_client") is not None
