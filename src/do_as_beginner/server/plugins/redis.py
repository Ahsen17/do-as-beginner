from typing import TYPE_CHECKING

from do_as_beginner.server.stores import ServerStore
from do_as_beginner.shared import RedisFactory

from .protocol import PluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.base import AppConfig


class RedisPlugin(PluginProtocol):
    """Server plugin for async redis"""

    def __init__(self, config: "AppConfig") -> None:

        self._config = config

    def setup(self) -> None:

        ServerStore.add_dependency(
            "redis_factory",
            RedisFactory(self._config.redis),
        )
