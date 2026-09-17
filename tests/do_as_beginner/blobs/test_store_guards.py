"""Async guard tests that never touch the async connection (SQLite-safe).

Size/key guards raise *before* any ORM access, so they run under the plain
SQLite test database without ``async_atomic``/``async_connections``. Paths that
do reach the database (real put/get, dedup, reference counts) belong to the
PG-marked integration tests.
"""

import pytest

from do_as_beginner.blobs.exceptions import BlobTooLargeError, BlobValidationError
from do_as_beginner.blobs.storage import DatabaseBlobStore


async def test_put_rejects_oversized_content_before_any_io() -> None:
    store = DatabaseBlobStore(max_blob_bytes=8)

    with pytest.raises(BlobTooLargeError, match="exceeds the 8-byte limit"):
        await store.put(b"0123456789")


async def test_get_rejects_invalid_key_before_any_io() -> None:
    store = DatabaseBlobStore(max_blob_bytes=8)

    with pytest.raises(BlobValidationError, match="Invalid blob key"):
        await store.get("nothex")


async def test_info_rejects_invalid_key_before_any_io() -> None:
    store = DatabaseBlobStore(max_blob_bytes=8)

    with pytest.raises(BlobValidationError, match="Invalid blob key"):
        await store.info("nothex")


async def test_exists_invalid_key_is_false_without_io() -> None:
    store = DatabaseBlobStore(max_blob_bytes=8)

    assert await store.exists("nothex") is False
