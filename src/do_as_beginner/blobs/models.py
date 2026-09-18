"""Content-addressed blob models.

All ORM access on the async path goes through the ``async_objects`` manager
(injected onto every model at runtime by ``django_async_backend.db.models.patch``)
so that reads and writes share the connection -- and therefore the transaction --
managed by ``django_async_backend.db.transaction.async_atomic()``.
"""

import asyncio
import hashlib

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, models
from django.db.models import F
from django_async_backend.db.transaction import async_atomic

from do_as_beginner.blobs.async_orm import async_manager

__all__ = (
    "Blob",
    "BlobReference",
)


class Blob(models.Model):
    """Content-addressed blob: sha256 key + bytea content."""

    key: models.CharField = models.CharField(max_length=64, unique=True, editable=False)
    content: models.BinaryField = models.BinaryField(editable=False)
    size: models.PositiveBigIntegerField = models.PositiveBigIntegerField(editable=False)
    content_type: models.CharField = models.CharField(  # noqa: DJ001  (nullable by frozen contract)
        max_length=255,
        blank=True,
        null=True,
    )
    reference_count: models.PositiveIntegerField = models.PositiveIntegerField(default=0)
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(size__gte=0), name="dab_blobs_blob_size_gte_0"),
            models.CheckConstraint(condition=models.Q(reference_count__gte=0), name="dab_blobs_blob_refcount_gte_0"),
        ]

    def __str__(self) -> str:

        return str(self.key)

    @classmethod
    async def acreate_from_content(cls, content: bytes, *, content_type: str | None = None) -> "Blob":
        """Return the blob row for ``content``, creating it on first sight (dedup-aware).

        The INSERT runs inside a nested savepoint so a concurrent creator hitting
        the unique ``key`` constraint can fall back to a re-read without aborting
        the surrounding transaction.
        """

        key = (await asyncio.to_thread(hashlib.sha256, content)).hexdigest()
        query = async_manager(cls).filter(key=key)
        existing: Blob | None = await query.afirst()
        if existing is not None:
            return existing

        try:
            async with async_atomic():
                return await async_manager(cls).acreate(
                    key=key,
                    content=content,
                    size=len(content),
                    content_type=content_type,
                )
        except IntegrityError as exc:
            # A concurrent transaction created the same content first; its row
            # is committed (or will be) and visible after the savepoint rollback.
            try:
                winner: Blob = await async_manager(cls).aget(key=key)
            except cls.DoesNotExist:
                # Not a unique-constraint race (or the winner rolled back):
                # surface the original database error, not a misleading miss.
                raise exc from None
            return winner


class BlobReference(models.Model):
    """Reference from a business object to a blob (generic relation).

    Reference counting is explicit (never signal-driven): create rows through
    :meth:`acreate_tracked` and delete them only via
    ``BlobService.release`` / ``purge_references``. Raw ORM ``acreate`` /
    ``adelete`` bypass counting and break the count invariant.
    """

    blob: models.ForeignKey = models.ForeignKey(
        Blob, on_delete=models.PROTECT, related_name="references", editable=False
    )
    content_type: models.ForeignKey = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+", editable=False
    )
    object_id: models.PositiveBigIntegerField = models.PositiveBigIntegerField(editable=False)
    field: models.CharField = models.CharField(max_length=64, default="", blank=True)
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)

    #: Runtime attribute contributed by the ``blob`` foreign key (typing-only here).
    blob_id: int

    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("content_type", "object_id", "field", "blob"),
                name="dab_blobs_blobreference_uniq",
            )
        ]
        indexes = [
            models.Index(fields=("content_type", "object_id"), name="dab_blobs_blobref_object_idx"),
        ]

    def __str__(self) -> str:

        return f"{self.content_type}/{self.object_id}[{self.field or '-'}] -> {self.blob.key}"

    @classmethod
    async def acreate_tracked(
        cls,
        *,
        blob: Blob,
        content_type: ContentType,
        object_id: int,
        field: str = "",
    ) -> "BlobReference":
        """Create a reference row and bump the blob count in the caller's transaction.

        Reference counting is explicit (never signal-driven): the count update runs
        in the same task and transaction as the row insert.
        """

        # Lock-order note: the count UPDATE takes the blob row's NO KEY UPDATE lock
        # *before* the reference INSERT acquires its FOR KEY SHARE lock on the same
        # row. That keeps every transaction's first blob-row lock the same kind
        # (see release()), closing the attach x release deadlock window.
        await async_manager(Blob).filter(pk=blob.pk).aupdate(reference_count=F("reference_count") + 1)
        reference: BlobReference = await async_manager(cls).acreate(
            blob=blob, content_type=content_type, object_id=object_id, field=field
        )
        return reference
