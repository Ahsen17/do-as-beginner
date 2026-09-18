from typing import TYPE_CHECKING

from qdrant_client import AsyncQdrantClient

from do_as_beginner.base import AppConfig
from do_as_beginner.server.core import AppPluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.server.depi import Container


class QdrantPlugin(AppPluginProtocol):
    """Server plugin for qdrant"""

    def on_app_init(self, container: "Container") -> None:

        container.register(
            AsyncQdrantClient(
                **AppConfig.load().qdrant.to_dict(exclude_unset=True),
            ),
            key="qdrant_client",
        )
