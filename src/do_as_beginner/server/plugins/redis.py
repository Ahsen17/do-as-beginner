from typing import TYPE_CHECKING

from do_as_beginner.shared import RedisFactory

from .protocol import PluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.base import AppConfig
    from do_as_beginner.server import DIContainer


class RedisPlugin(PluginProtocol):
    """Server plugin for async redis"""

    def __init__(self, config: "AppConfig", container: "DIContainer") -> None:

        self._config = config
        self._container = container

    def setup(self) -> None:

        self._container.register(
            RedisFactory(self._config.redis),
            key="redis_factory",
        )
