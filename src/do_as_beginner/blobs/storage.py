"""``BlobStore`` protocol and the database (bytea) backend."""

from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

from do_as_beginner.blobs.async_orm import async_manager
from do_as_beginner.blobs.dto import BlobInfo, info_from_values
from do_as_beginner.blobs.exceptions import BlobNotFoundError, BlobTooLargeError, BlobValidationError
from do_as_beginner.blobs.models import Blob

if TYPE_CHECKING:
    from datetime import datetime

__all__ = (
    "BlobStore",
    "DatabaseBlobStore",
)


DEFAULT_MAX_BLOB_BYTES: int = 64 * 1024 * 1024
_HEX_DIGITS = frozenset("0123456789abcdef")


def normalize_key(key: str) -> str:
    """Normalize and validate a blob key (sha256 hex, case- and space-insensitive)."""

    normalized = key.strip().lower()
    if len(normalized) != 64 or not set(normalized) <= _HEX_DIGITS:
        msg = f"Invalid blob key: {key!r}"
        raise BlobValidationError(msg)
    return normalized


@runtime_checkable
class BlobStore(Protocol):
    """Backend-agnostic blob storage surface (references are a facade concern)."""

    async def put(self, content: bytes, *, content_type: str | None = None) -> Blob:
        """Store (or dedup-hit) ``content`` and return the blob row."""
        ...

    async def get(self, key: str, *, max_size: int | None = None) -> bytes:
        """Return the full content of the blob ``key``."""
        ...

    async def exists(self, key: str) -> bool:
        """Return whether ``key`` is stored (never raises a domain error)."""
        ...

    async def info(self, key: str) -> BlobInfo:
        """Return the metadata snapshot of ``key`` without loading the content."""
        ...


class DatabaseBlobStore:
    """Content-addressed bytea backend backed by the :class:`Blob` model."""

    def __init__(self, max_blob_bytes: int = DEFAULT_MAX_BLOB_BYTES) -> None:
        if max_blob_bytes <= 0:
            msg = f"max_blob_bytes must be positive, got {max_blob_bytes}"
            raise BlobValidationError(msg)
        self._max_blob_bytes = max_blob_bytes

    async def put(self, content: bytes, *, content_type: str | None = None) -> Blob:
        """Store (or dedup-hit) ``content``; joins the caller's transaction."""

        if len(content) > self._max_blob_bytes:
            msg = f"Content of {len(content)} bytes exceeds the {self._max_blob_bytes}-byte limit"
            raise BlobTooLargeError(msg)
        return await Blob.acreate_from_content(content, content_type=content_type)

    async def get(self, key: str, *, max_size: int | None = None) -> bytes:
        """Return the full content of ``key``; guard reads with ``max_size``.

        The size check runs on a projection *before* the content is loaded, so an
        oversized read never brings the bytes into memory.
        """

        normalized = normalize_key(key)
        try:
            row: dict[str, Any] = await async_manager(Blob).filter(key=normalized).values("size").aget(key=normalized)
        except Blob.DoesNotExist as exc:
            raise BlobNotFoundError(f"Blob {normalized!r} does not exist") from exc
        size = int(row["size"])
        if max_size is not None and size > max_size:
            msg = f"Blob {normalized!r} is {size} bytes, above the {max_size}-byte read guard"
            raise BlobTooLargeError(msg)
        try:
            blob: Blob = await async_manager(Blob).aget(key=normalized)
        except Blob.DoesNotExist as exc:  # pragma: no cover - deleted between the two reads
            raise BlobNotFoundError(f"Blob {normalized!r} does not exist") from exc
        return bytes(blob.content)

    async def exists(self, key: str) -> bool:
        """Return whether ``key`` is stored; invalid keys simply do not exist."""

        try:
            normalized = normalize_key(key)
        except BlobValidationError:
            return False
        found: Blob | None = await async_manager(Blob).filter(key=normalized).afirst()
        return found is not None

    async def info(self, key: str) -> BlobInfo:
        """Return metadata for ``key``; the content column is never loaded."""

        normalized = normalize_key(key)
        try:
            row: dict[str, Any] = (
                await async_manager(Blob)
                .filter(key=normalized)
                .values("key", "size", "content_type", "reference_count", "created_at")
                .aget(key=normalized)
            )
        except Blob.DoesNotExist as exc:
            raise BlobNotFoundError(f"Blob {normalized!r} does not exist") from exc
        return info_from_values(
            key=str(row["key"]),
            size=int(row["size"]),
            content_type=cast("str | None", row["content_type"]),
            reference_count=int(row["reference_count"]),
            created_at=cast("datetime", row["created_at"]),
        )
