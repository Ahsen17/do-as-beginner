"""Unit tests for plugin DI registration (Redis/Qdrant/Blobs wire into the container)."""

from do_as_beginner.base import AppConfig
from do_as_beginner.base.config.blobs import BlobsConfig
from do_as_beginner.blobs import BlobService
from do_as_beginner.server.depi import Container
from do_as_beginner.server.plugins import BlobsPlugin, QdrantPlugin, RedisPlugin
from do_as_beginner.shared import RedisFactory


def test_redis_plugin_registers_singleton_into_container(default_container: Container) -> None:
    config = AppConfig.load()

    RedisPlugin(config).setup()

    factory: RedisFactory = default_container.get("redis_factory")
    assert isinstance(factory, RedisFactory)
    # type-first lookup hits the same singleton
    assert default_container.get(RedisFactory) is factory


def test_qdrant_plugin_registers_into_container(default_container: Container) -> None:
    config = AppConfig.load()

    QdrantPlugin(config).setup()

    assert default_container.get("qdrant_client") is not None


def test_blobs_plugin_registers_lazy_service_factory(default_container: Container) -> None:
    config = AppConfig.load()

    BlobsPlugin(config).setup()

    factory = default_container.get("blob_service_factory")
    assert isinstance(factory.create(), BlobService)


def test_blobs_plugin_uses_configured_limit(default_container: Container) -> None:
    config = AppConfig.load()
    config.blobs = BlobsConfig(max_blob_bytes=4096)

    BlobsPlugin(config).setup()

    service = default_container.get("blob_service_factory").create()
    assert service._store._max_blob_bytes == 4096
