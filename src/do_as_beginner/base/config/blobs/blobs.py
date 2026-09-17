"""Blob storage configuration."""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from do_as_beginner.base.schemas import BaseStruct

__all__ = ("BlobsConfig",)


class BlobsConfig(BaseStruct):
    """Configuration for the blob-storage module (``config.yaml`` ``blobs:`` section)."""

    model_config = ConfigDict(extra="forbid")

    backend: Literal["database"] = "database"
    max_blob_bytes: int = Field(default=64 * 1024 * 1024, gt=0)
    options: dict[str, Any] = Field(default_factory=dict)
