from typing import TYPE_CHECKING

from qdrant_client import AsyncQdrantClient

from do_as_beginner.server import ServerStore

from .protocol import PluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.base import AppConfig


class QdrantPlugin(PluginProtocol):
    """Server plugin for qdrant"""

    def __init__(self, config: "AppConfig") -> None:

        self._config = config

    def setup(self) -> None:

        ServerStore.add_dependency(
            "qdrant_client",
            AsyncQdrantClient(
                **self._config.qdrant.to_dict(
                    exclude_unset=True,
                )
            ),
        )
