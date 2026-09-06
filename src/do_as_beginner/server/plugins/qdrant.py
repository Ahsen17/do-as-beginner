from typing import TYPE_CHECKING

from qdrant_client import AsyncQdrantClient

from .protocol import PluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.base import AppConfig
    from do_as_beginner.server import DIContainer


class QdrantPlugin(PluginProtocol):
    """Server plugin for qdrant"""

    def __init__(self, config: "AppConfig", container: "DIContainer") -> None:

        self._config = config
        self._container = container

    def setup(self) -> None:

        self._container.register(
            AsyncQdrantClient(
                **self._config.qdrant.to_dict(
                    exclude_unset=True,
                )
            ),
            key="qdrant_client",
        )
