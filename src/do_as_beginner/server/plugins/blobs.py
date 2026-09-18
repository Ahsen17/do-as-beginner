from typing import TYPE_CHECKING

from do_as_beginner.base import AppConfig
from do_as_beginner.blobs.factory import BlobServiceFactory
from do_as_beginner.server.core import AppPluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.server.depi import Container


class BlobsPlugin(AppPluginProtocol):
    """Server plugin for the blob-storage facade (setup facet: DI registration)."""

    def on_app_init(self, container: "Container") -> None:

        container.register(
            BlobServiceFactory(AppConfig.load().blobs),
            key="blob_service_factory",
        )
