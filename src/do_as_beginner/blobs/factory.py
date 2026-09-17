"""Factory for the blob-storage facade."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from do_as_beginner.base.config.blobs import BlobsConfig
    from do_as_beginner.blobs.service import BlobService

__all__ = ("BlobServiceFactory",)


class BlobServiceFactory:
    """Factory for :class:`BlobService`.

    Model imports are deferred to :meth:`create` because this module is imported
    during plugin setup, which runs before ``django.setup()`` populates the app
    registry.
    """

    def __init__(self, config: "BlobsConfig") -> None:

        self._config = config

    def create(self) -> "BlobService":

        from do_as_beginner.blobs import BlobService, DatabaseBlobStore  # noqa: PLC0415

        return BlobService(DatabaseBlobStore(self._config.max_blob_bytes))
