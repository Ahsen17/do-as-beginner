"""PG-marked integration tests: the minimal strong-consistency subset (R9).

These run against the *default* alias, which ``conftest.py`` points at the real
PostgreSQL (``django_async_backend`` + async-ORM path) when ``DAB_TEST_PG_DSN``
is set; without the variable every test here skips (SQLite cannot exercise
``async_atomic`` or the async signal receivers).
"""

import hashlib
import os
import threading
import time
from collections.abc import AsyncIterator
from uuid import uuid4

import psycopg
import pytest
from django.contrib.contenttypes.models import ContentType
from django_async_backend.db.transaction import async_atomic

from do_as_beginner.base.config.blobs import BlobsConfig
from do_as_beginner.blobs.async_orm import async_manager
from do_as_beginner.blobs.exceptions import BlobNotFoundError, BlobTooLargeError
from do_as_beginner.blobs.factory import BlobServiceFactory
from do_as_beginner.blobs.models import Blob, BlobReference
from do_as_beginner.blobs.service import BlobService

pytestmark = [pytest.mark.pg]

_PG_DSN = os.environ.get("DAB_TEST_PG_DSN", "")


@pytest.fixture
def _require_pg() -> None:
    if not _PG_DSN:
        pytest.skip("DAB_TEST_PG_DSN not set; PG integration tests are disabled")


@pytest.fixture
async def _clean_tables(_require_pg: None) -> AsyncIterator[None]:
    yield
    await async_manager(BlobReference).filter().adelete()
    await async_manager(Blob).filter().adelete()
    # Reset per-task async connections: django-async-backend binds each connection
    # to the task that first used it, so the next test's task needs a fresh one.
    from django_async_backend.db import async_connections  # noqa: PLC0415

    for conn in async_connections.all(initialized_only=True):
        try:
            await conn.close()
        except RuntimeError:
            pass  # owned by another task; the wrapper is evicted below regardless
        delattr(async_connections._connections, conn.alias)


@pytest.fixture
async def service(_clean_tables: None) -> BlobService:
    return BlobServiceFactory(BlobsConfig(max_blob_bytes=1024 * 1024)).create()


async def _seed_subject() -> Blob:
    """Create a blob row used as the attach *subject* (int pk + registered ContentType)."""
    return await Blob.acreate_from_content(b"subject-" + uuid4().bytes)


async def test_put_and_attach_is_atomic_and_visible(service: BlobService) -> None:
    subject = await _seed_subject()
    content = b"atomic-" + uuid4().bytes

    info, reference = await service.put_and_attach(content, obj=subject)

    assert info.size == len(content)
    assert info.checksum == info.key
    assert await service.get(info.key) == content
    assert (await service.info(info.key)).reference_count == 1
    assert reference.blob.key == info.key


async def test_rolled_back_transaction_leaves_nothing_behind(service: BlobService) -> None:
    subject = await _seed_subject()
    content = b"rollback-" + uuid4().bytes
    key = hashlib.sha256(content).hexdigest()

    class _Boom(Exception): ...

    with pytest.raises(_Boom):
        async with async_atomic():
            await service.put_and_attach(content, obj=subject)
            raise _Boom

    assert await async_manager(Blob).filter(key=key).acount() == 0
    assert await async_manager(BlobReference).filter(object_id=subject.pk).acount() == 0


async def test_dedup_stores_identical_content_once(service: BlobService) -> None:
    content = b"dedup-" + uuid4().bytes

    first = await Blob.acreate_from_content(content)
    second = await Blob.acreate_from_content(content)

    assert first.pk == second.pk
    assert await async_manager(Blob).filter(key=first.key).acount() == 1


async def test_reference_count_invariant_across_release(service: BlobService) -> None:
    subject = await _seed_subject()
    info = await service.put(b"counted-" + uuid4().bytes)

    first = await service.attach(info.key, obj=subject, field="a")
    second = await service.attach(info.key, obj=subject, field="b")
    assert (await service.info(info.key)).reference_count == 2

    await service.release(first)
    assert (await service.info(info.key)).reference_count == 1

    await service.release(second)
    with pytest.raises(BlobNotFoundError):
        await service.info(info.key)


async def test_discard_only_removes_unreferenced_blobs(service: BlobService) -> None:
    subject = await _seed_subject()

    orphan = await service.put(b"orphan-" + uuid4().bytes)
    assert await service.discard(orphan.key) is True
    assert not await service.exists(orphan.key)

    kept = await service.put(b"kept-" + uuid4().bytes)
    reference = await service.attach(kept.key, obj=subject)
    assert await service.discard(kept.key) is False
    await service.release(reference)


async def test_concurrent_put_falls_back_to_existing_row(service: BlobService) -> None:
    """A concurrent creator that commits while our INSERT waits on the unique
    index must resolve to the already-committed row (savepoint fallback)."""
    content = b"race-" + uuid4().bytes
    key = hashlib.sha256(content).hexdigest()

    with psycopg.connect(_PG_DSN) as ext, ext.cursor() as cur:
        cur.execute(
            "INSERT INTO dab_blobs_blob (key, content, size, reference_count, created_at, updated_at) "
            "VALUES (%s, %s, %s, 0, NOW(), NOW()) RETURNING id",
            (key, content, len(content)),
        )
        external_id = cur.fetchone()[0]  # type: ignore[index]  # RETURNING always yields a row

        def _commit_external() -> None:
            time.sleep(0.2)
            ext.commit()

        threading.Thread(target=_commit_external, daemon=True).start()
        winner = await Blob.acreate_from_content(content)

    assert winner.key == key
    assert winner.pk == external_id  # the committed concurrent row, not a recreate
    assert await async_manager(Blob).filter(key=key).acount() == 1


async def test_get_max_size_guard_rejects_before_load(service: BlobService) -> None:
    content = b"guarded-" + uuid4().bytes
    info = await service.put(content)

    with pytest.raises(BlobTooLargeError, match="read guard"):
        await service.get(info.key, max_size=4)
    assert await service.get(info.key, max_size=info.size) == content


async def test_attach_is_idempotent_on_same_target(service: BlobService) -> None:
    subject = await _seed_subject()
    info = await service.put(b"idem-" + uuid4().bytes)

    first = await service.attach(info.key, obj=subject, field="same")
    second = await service.attach(info.key, obj=subject, field="same")

    assert first.pk == second.pk
    assert (await service.info(info.key)).reference_count == 1


async def test_purge_references_keeps_shared_blob_and_frees_exhausted_one(
    service: BlobService,
) -> None:
    other = await _seed_subject()
    info = await service.put(b"purged-" + uuid4().bytes)
    await service.attach(info.key, obj=other, field="a")
    await service.attach(info.key, obj=other, field="b")

    subject = await _seed_subject()
    await service.attach(info.key, obj=subject, field="c")

    # Purging one of two subjects decrements but keeps the shared blob.
    assert await service.purge_references(other) == 2
    assert (await service.info(info.key)).reference_count == 1

    # Purging the last subject deletes the blob in the same transaction.
    assert await service.purge_references(subject) == 1
    with pytest.raises(BlobNotFoundError):
        await service.info(info.key)


async def test_attach_falls_back_when_reference_created_concurrently(
    service: BlobService,
) -> None:
    """A concurrent creator that commits while our reference INSERT waits on the
    unique index must resolve to the committed reference row (idempotent)."""
    subject = await _seed_subject()
    info = await service.put(b"refrace-" + uuid4().bytes)
    blob = await async_manager(Blob).aget(key=info.key)
    ctype = await async_manager(ContentType).aget(
        app_label=Blob._meta.app_label, model=Blob._meta.model_name
    )

    with psycopg.connect(_PG_DSN) as ext, ext.cursor() as cur:
        # Simulate a *real* concurrent attach: insert + count bump in one transaction.
        cur.execute(
            "INSERT INTO dab_blobs_blobreference (blob_id, content_type_id, object_id, field, created_at) "
            "VALUES (%s, %s, %s, 'race', NOW()) RETURNING id",
            (blob.pk, ctype.pk, subject.pk),
        )
        external_id = cur.fetchone()[0]  # type: ignore[index]  # RETURNING always yields a row
        cur.execute(
            "UPDATE dab_blobs_blob SET reference_count = reference_count + 1 WHERE id = %s",
            (blob.pk,),
        )
        def _commit_external() -> None:
            time.sleep(0.2)
            ext.commit()

        threading.Thread(target=_commit_external, daemon=True).start()
        reference = await service.attach(info.key, obj=subject, field="race")

    assert reference.pk == external_id
    assert (await service.info(info.key)).reference_count == 1
