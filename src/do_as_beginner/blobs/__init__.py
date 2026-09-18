"""Blob content storage for dab: content-addressed bytea storage behind a
backend-agnostic async facade (see ``.runtime/tasks/1789109005/docs/api.md``).
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .apps import BlobsAppConfig
from .dto import BlobInfo
from .exceptions import (
    BlobBackendError,
    BlobIntegrityError,
    BlobNotFoundError,
    BlobReferenceError,
    BlobStoreError,
    BlobTooLargeError,
    BlobValidationError,
)

if TYPE_CHECKING:
    from .factory import BlobServiceFactory
    from .models import Blob, BlobReference
    from .service import BlobService
    from .storage import BlobStore, DatabaseBlobStore

__all__ = (
    "Blob",
    "BlobBackendError",
    "BlobInfo",
    "BlobIntegrityError",
    "BlobNotFoundError",
    "BlobReference",
    "BlobReferenceError",
    "BlobService",
    "BlobServiceFactory",
    "BlobStore",
    "BlobStoreError",
    "BlobTooLargeError",
    "BlobValidationError",
    "BlobsAppConfig",
    "DatabaseBlobStore",
)

#: Model/facade classes transitively import ``models``, which Django must not
#: see while it is still importing app packages (``apps_ready`` is false during
#: ``apps.populate()``). Defer those imports to first attribute access.
_LAZY_ATTRS: dict[str, str] = {
    "Blob": "models",
    "BlobReference": "models",
    "BlobService": "service",
    "BlobServiceFactory": "factory",
    "BlobStore": "storage",
    "DatabaseBlobStore": "storage",
}


def __getattr__(name: str) -> Any:

    module_name = _LAZY_ATTRS.get(name)
    if module_name is not None:
        return getattr(import_module(f"{__name__}.{module_name}"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
