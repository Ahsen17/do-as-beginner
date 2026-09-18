"""``BlobService`` facade: orchestration, reference management, transaction boundaries.

Write methods manage their own transaction via
``django_async_backend.db.transaction.async_atomic()``; when called inside an
existing transaction they join it (nested = savepoint), so service-path and
model-path writes compose.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, OperationalError, models
from django.db.models import F
from django_async_backend.db.transaction import async_atomic

from do_as_beginner.blobs.async_orm import async_manager
from do_as_beginner.blobs.dto import BlobInfo, info_from_values
from do_as_beginner.blobs.exceptions import (
    BlobBackendError,
    BlobIntegrityError,
    BlobNotFoundError,
    BlobReferenceError,
    BlobValidationError,
)
from do_as_beginner.blobs.models import Blob, BlobReference
from do_as_beginner.blobs.storage import BlobStore, normalize_key

__all__ = ("BlobService",)

_MAX_FIELD_LENGTH: int = int(getattr(BlobReference._meta.get_field("field"), "max_length", 64))


def _to_info(blob: Blob) -> BlobInfo:
    """Project a blob row onto the facade DTO."""

    return info_from_values(
        key=blob.key,
        size=blob.size,
        content_type=blob.content_type,
        reference_count=blob.reference_count,
        created_at=blob.created_at,
    )


def _validate_attach_target(obj: models.Model, field: str) -> None:
    """Validate the attach target (saved integer-pk object, bounded field name)."""

    if len(field) > _MAX_FIELD_LENGTH:
        msg = f"field exceeds the {_MAX_FIELD_LENGTH}-character limit"
        raise BlobValidationError(msg)
    if obj.pk is None or not isinstance(obj.pk, int):
        msg = "obj must be saved with an integer primary key before attaching"
        raise BlobValidationError(msg)


@asynccontextmanager
async def _backend_errors() -> AsyncIterator[None]:
    """Wrap database errors that escape to the facade as ``BlobBackendError``.

    Domain errors raised deliberately inside (unique-race fallbacks, FK-race
    mapping) are converted before this wrapper sees them; what escapes here is a
    genuine unexpected database failure (including deadlock aborts).
    """

    try:
        yield
    except (IntegrityError, OperationalError) as exc:
        raise BlobBackendError(str(exc)) from exc


class BlobService:
    """User-facing facade over a :class:`BlobStore` plus reference management."""

    def __init__(self, store: BlobStore) -> None:

        self._store = store

    async def put(self, content: bytes, *, content_type: str | None = None) -> BlobInfo:
        """Store (or dedup-hit) ``content`` and return its metadata."""

        async with _backend_errors(), async_atomic():
            blob: Blob = await self._store.put(content, content_type=content_type)
        return _to_info(blob)

    async def attach(self, key: str, *, obj: models.Model, field: str = "") -> BlobReference:
        """Create (or idempotently return) the reference from ``obj`` to ``key``."""

        normalized = normalize_key(key)
        _validate_attach_target(obj, field)
        async with _backend_errors(), async_atomic():
            return await self._attach_in_transaction(normalized, obj=obj, field=field)

    async def put_and_attach(
        self,
        content: bytes,
        *,
        obj: models.Model,
        field: str = "",
        content_type: str | None = None,
    ) -> tuple[BlobInfo, BlobReference]:
        """Store ``content`` and attach it to ``obj`` atomically (strong-consistency entry)."""

        _validate_attach_target(obj, field)
        async with _backend_errors(), async_atomic():
            blob: Blob = await self._store.put(content, content_type=content_type)
            reference = await self._attach_in_transaction(blob.key, obj=obj, field=field)
        return _to_info(blob), reference

    async def get(self, key: str, *, max_size: int | None = None) -> bytes:
        """Read the full content of ``key``."""

        return await self._store.get(key, max_size=max_size)

    async def info(self, key: str) -> BlobInfo:
        """Return the metadata snapshot of ``key``."""

        return await self._store.info(key)

    async def exists(self, key: str) -> bool:
        """Return whether ``key`` is stored."""

        return await self._store.exists(key)

    async def release(self, reference: BlobReference) -> None:
        """Delete ``reference`` and decrement the blob count in the same transaction.

        When the released reference was the last one, the blob row is deleted in
        the same transaction.
        """

        # The negative-count guard below is a backstop; the primary defence is the
        # dab_blobs_blob_refcount_gte_0 CHECK constraint, which fires on the UPDATE.
        async with _backend_errors(), async_atomic():
            deleted, _ = await async_manager(BlobReference).filter(pk=reference.pk).adelete()
            if not deleted:
                msg = f"Reference {reference.pk} is already gone (concurrent release?)"
                raise BlobReferenceError(msg)

            await async_manager(Blob).filter(pk=reference.blob_id).aupdate(reference_count=F("reference_count") - 1)
            blob: Blob = await async_manager(Blob).aget(pk=reference.blob_id)
            if blob.reference_count < 0:
                msg = f"Reference count for blob {blob.key!r} went negative"
                raise BlobIntegrityError(msg)
            if blob.reference_count == 0:
                await async_manager(Blob).filter(pk=blob.pk).adelete()

    async def discard(self, key: str) -> bool:
        """Delete the blob ``key`` only when it has no references; return whether it happened."""

        normalized = normalize_key(key)
        async with _backend_errors(), async_atomic():
            deleted, _ = await async_manager(Blob).filter(key=normalized, reference_count=0).adelete()
        return deleted > 0

    async def purge_references(self, obj: models.Model) -> int:
        """Delete every reference of ``obj``, decrementing counts in the same transaction.

        Deleting a business object that carries references must go through here
        (or ``release``): raw queryset deletes bypass counting and desynchronise
        the reference-count invariant.
        """

        ctype: ContentType = await async_manager(ContentType).aget(
            app_label=type(obj)._meta.app_label, model=type(obj)._meta.model_name
        )
        total = 0
        async with _backend_errors(), async_atomic():
            while True:
                reference: BlobReference | None = (
                    await async_manager(BlobReference).filter(content_type=ctype, object_id=obj.pk).afirst()
                )
                if reference is None:
                    break
                await async_manager(BlobReference).filter(pk=reference.pk).adelete()
                await async_manager(Blob).filter(pk=reference.blob_id).aupdate(reference_count=F("reference_count") - 1)
                blob: Blob = await async_manager(Blob).aget(pk=reference.blob_id)
                if blob.reference_count < 0:
                    msg = f"Reference count for blob {blob.key!r} went negative"
                    raise BlobIntegrityError(msg)
                if blob.reference_count == 0:
                    await async_manager(Blob).filter(pk=blob.pk).adelete()
                total += 1
        return total

    async def _attach_in_transaction(self, normalized_key: str, *, obj: models.Model, field: str) -> BlobReference:
        """Create the reference row; caller must already be inside ``async_atomic``."""

        try:
            blob: Blob = await async_manager(Blob).aget(key=normalized_key)
        except Blob.DoesNotExist as exc:
            raise BlobNotFoundError(f"Blob {normalized_key!r} does not exist") from exc

        ctype: ContentType = await async_manager(ContentType).aget(
            app_label=type(obj)._meta.app_label, model=type(obj)._meta.model_name
        )
        query = async_manager(BlobReference).filter(blob=blob, content_type=ctype, object_id=obj.pk, field=field)
        existing: BlobReference | None = await query.afirst()
        if existing is not None:
            return existing

        try:
            async with async_atomic():  # nested -> savepoint
                return await BlobReference.acreate_tracked(blob=blob, content_type=ctype, object_id=obj.pk, field=field)
        except IntegrityError:
            # Either a concurrent attach created the same reference (idempotent)
            # or the blob was concurrently released (FK violation). Tell them apart.
            try:
                await async_manager(Blob).aget(key=normalized_key)
            except Blob.DoesNotExist as exc:
                raise BlobNotFoundError(f"Blob {normalized_key!r} was concurrently released") from exc
            winner: BlobReference | None = await query.afirst()
            if winner is None:
                msg = f"Reference race for blob {normalized_key!r} resolved to nothing"
                raise BlobReferenceError(msg) from None
            return winner
