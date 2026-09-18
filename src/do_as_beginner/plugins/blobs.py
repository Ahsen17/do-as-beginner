from typing import TYPE_CHECKING

from do_as_beginner.blobs.factory import BlobServiceFactory
from do_as_beginner.server import AppPluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.base import AppConfig
    from do_as_beginner.server import Container


class BlobsPlugin(AppPluginProtocol):
    """Server plugin for the blob-storage facade (setup facet: DI registration)."""

    name = "blobs"

    def __init__(self, config: "AppConfig") -> None:

        self._config = config

    def on_app_init(self, container: "Container") -> None:

        container.register(
            BlobServiceFactory(self._config.blobs),
            key="blob_service_factory",
        )
