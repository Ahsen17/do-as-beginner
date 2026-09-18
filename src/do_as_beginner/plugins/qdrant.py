from typing import TYPE_CHECKING

from qdrant_client import AsyncQdrantClient

from do_as_beginner.server import AppPluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.base import AppConfig
    from do_as_beginner.server import Container


class QdrantPlugin(AppPluginProtocol):
    """Server plugin for qdrant"""

    def __init__(self, config: "AppConfig") -> None:

        self._config = config

    def on_app_init(self, container: "Container") -> None:

        container.register(
            AsyncQdrantClient(
                **self._config.qdrant.to_dict(exclude_unset=True),
            ),
            key="qdrant_client",
        )
