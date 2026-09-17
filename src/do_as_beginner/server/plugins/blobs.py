from typing import TYPE_CHECKING

from do_as_beginner.blobs.factory import BlobServiceFactory

from .protocol import PluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.base import AppConfig
    from do_as_beginner.server import DIContainer


class BlobsPlugin(PluginProtocol):
    """Server plugin for the blob-storage facade"""

    def __init__(self, config: "AppConfig", container: "DIContainer") -> None:

        self._config = config
        self._container = container

    def setup(self) -> None:

        self._container.register(
            BlobServiceFactory(self._config.blobs),
            key="blob_service_factory",
        )
