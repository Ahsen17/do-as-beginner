from typing import TYPE_CHECKING

from do_as_beginner.blobs.factory import BlobServiceFactory
from do_as_beginner.server.depi import DI

from .protocol import PluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.base import AppConfig


class BlobsPlugin(PluginProtocol):
    """Server plugin for the blob-storage facade"""

    def __init__(self, config: "AppConfig") -> None:
        self._config = config

    def setup(self) -> None:
        DI.get_default_container().register(
            BlobServiceFactory(self._config.blobs),
            key="blob_service_factory",
        )
