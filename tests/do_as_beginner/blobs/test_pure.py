"""Unit tests for pure blob-storage logic (no async connection needed)."""

import pytest
from pydantic import ValidationError

from do_as_beginner.base.config.blobs import BlobsConfig
from do_as_beginner.blobs.dto import BlobInfo
from do_as_beginner.blobs.exceptions import (
    BlobBackendError,
    BlobIntegrityError,
    BlobNotFoundError,
    BlobReferenceError,
    BlobStoreError,
    BlobTooLargeError,
    BlobValidationError,
)
from do_as_beginner.blobs.factory import BlobServiceFactory
from do_as_beginner.blobs.service import BlobService
from do_as_beginner.blobs.storage import DEFAULT_MAX_BLOB_BYTES, DatabaseBlobStore, normalize_key

UPPER_KEY = "  " + ("AB" * 32) + "  "
BAD_KEYS = ("nothex", "zz" * 32, "ab" * 31, "ab" * 33, "")


def test_normalize_key_strips_and_lowercases() -> None:
    assert normalize_key(UPPER_KEY) == "ab" * 32


@pytest.mark.parametrize("bad", BAD_KEYS)
def test_normalize_key_rejects_invalid_input(bad: str) -> None:
    with pytest.raises(BlobValidationError):
        normalize_key(bad)


@pytest.mark.parametrize(
    ("exc", "base"),
    [
        (BlobValidationError, BlobStoreError),
        (BlobNotFoundError, BlobStoreError),
        (BlobReferenceError, BlobStoreError),
        (BlobIntegrityError, BlobStoreError),
        (BlobBackendError, BlobStoreError),
        (BlobTooLargeError, BlobValidationError),
    ],
)
def test_exception_hierarchy(exc: type[Exception], base: type[Exception]) -> None:
    assert issubclass(exc, base)


def test_database_blob_store_rejects_non_positive_limit() -> None:
    for bad in (0, -1):
        with pytest.raises(BlobValidationError, match="must be positive"):
            DatabaseBlobStore(max_blob_bytes=bad)


def test_database_blob_store_default_limit() -> None:
    assert DatabaseBlobStore()._max_blob_bytes == DEFAULT_MAX_BLOB_BYTES


def test_blob_info_dto_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        BlobInfo.model_validate(
            {
                "key": "ab" * 32,
                "size": 1,
                "checksum": "ab" * 32,
                "reference_count": 0,
                "created_at": "2026-01-01T00:00:00Z",
                "unexpected": "x",
            }
        )


def test_blobs_config_defaults() -> None:
    config = BlobsConfig()
    assert config.backend == "database"
    assert config.max_blob_bytes == DEFAULT_MAX_BLOB_BYTES
    assert config.options == {}


def test_blobs_config_rejects_non_positive_max_bytes() -> None:
    with pytest.raises(ValidationError):
        BlobsConfig(max_blob_bytes=0)


def test_blobs_config_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        BlobsConfig.model_validate({"unexpected": "x"})


def test_blob_service_factory_creates_configured_service() -> None:
    service = BlobServiceFactory(BlobsConfig(max_blob_bytes=1024)).create()
    assert isinstance(service, BlobService)
