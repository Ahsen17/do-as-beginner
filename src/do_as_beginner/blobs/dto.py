"""Data-transfer objects for the blob-storage facade."""

from datetime import datetime

from pydantic import ConfigDict

from do_as_beginner.base.schemas import BaseStruct

__all__ = ("BlobInfo", "info_from_values")


class BlobInfo(BaseStruct):
    """Metadata snapshot of a stored blob (never includes the content bytes)."""

    model_config = ConfigDict(extra="forbid")

    key: str
    size: int
    content_type: str | None = None
    checksum: str
    reference_count: int
    created_at: datetime


def info_from_values(
    *,
    key: str,
    size: int,
    content_type: str | None,
    reference_count: int,
    created_at: datetime,
) -> BlobInfo:
    """Project raw blob values onto the DTO (checksum == key, content-addressed)."""

    return BlobInfo(
        key=key,
        size=size,
        content_type=content_type,
        checksum=key,
        reference_count=reference_count,
        created_at=created_at,
    )
