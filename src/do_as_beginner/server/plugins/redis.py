from typing import TYPE_CHECKING

from do_as_beginner.base import AppConfig
from do_as_beginner.server.core import AppPluginProtocol
from do_as_beginner.shared import RedisFactory

if TYPE_CHECKING:
    from do_as_beginner.server.depi import Container


class RedisPlugin(AppPluginProtocol):
    """Server plugin for async redis (setup facet: DI registration)."""

    def on_app_init(self, container: "Container") -> None:

        container.register(
            RedisFactory(AppConfig.load().redis),
            key="redis_factory",
        )
