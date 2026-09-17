"""Exception hierarchy for the blob-storage module."""

__all__ = (
    "BlobBackendError",
    "BlobIntegrityError",
    "BlobNotFoundError",
    "BlobReferenceError",
    "BlobStoreError",
    "BlobTooLargeError",
    "BlobValidationError",
)


class BlobStoreError(Exception):
    """Base error for every blob-storage failure."""


class BlobValidationError(BlobStoreError):
    """Raised when an input to the storage API is invalid."""


class BlobTooLargeError(BlobValidationError):
    """Raised when content or a read exceeds the configured size limit."""


class BlobNotFoundError(BlobStoreError):
    """Raised when a blob key does not exist."""


class BlobReferenceError(BlobStoreError):
    """Raised on a concurrent reference loss (the caller may retry)."""


class BlobIntegrityError(BlobStoreError):
    """Raised when the reference-count invariant is violated (a defect, not retryable)."""


class BlobBackendError(BlobStoreError):
    """Raised when the underlying database/driver fails (original kept as ``__cause__``)."""
