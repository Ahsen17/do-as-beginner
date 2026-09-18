from typing import TYPE_CHECKING

from do_as_beginner.server import AppPluginProtocol
from do_as_beginner.shared import RedisFactory

if TYPE_CHECKING:
    from do_as_beginner.base import AppConfig
    from do_as_beginner.server import Container


class RedisPlugin(AppPluginProtocol):
    """Server plugin for async redis (setup facet: DI registration)."""

    def __init__(self, config: "AppConfig") -> None:

        self._config = config

    def on_app_init(self, container: "Container") -> None:

        container.register(
            RedisFactory(self._config.redis),
            key="redis_factory",
        )
