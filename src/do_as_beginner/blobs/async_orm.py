"""Typed façade over the ``async_objects`` manager injected by django-async-backend.

The upstream package ships no type information (its managers are patched onto
every model at runtime, see ``django_async_backend.db.models.patch``), so this
module gives the async-ORM surface the precise shape the storage code needs.
The runtime behaviour is upstream's: queries run on ``async_connections`` and
therefore join the transaction managed by ``async_atomic``.
"""

from collections.abc import Awaitable
from typing import Any, Protocol

from django.db.models import Model


class AsyncQuerySetT[T: Model](Protocol):
    """Subset of ``django_async_backend.db.models.query.AsyncQuerySet`` used here."""

    def afirst(self) -> Awaitable[T | None]:
        """Return the first row or ``None``."""
        raise NotImplementedError

    def aget(self, **kwargs: Any) -> Awaitable[T]:
        """Return exactly one row or raise ``DoesNotExist``."""
        raise NotImplementedError

    def acreate(self, **kwargs: Any) -> Awaitable[T]:
        """Insert a row and return the instance."""
        raise NotImplementedError

    def acount(self) -> Awaitable[int]:
        """Return the number of matching rows."""
        raise NotImplementedError

    def aupdate(self, **kwargs: Any) -> Awaitable[int]:
        """Update matching rows in place; return the number of affected rows."""
        raise NotImplementedError

    def adelete(self) -> Awaitable[tuple[int, dict[str, int]]]:
        """Delete matching rows; return ``(total, per-model counts)``."""
        raise NotImplementedError

    def filter(self, **kwargs: Any) -> "AsyncQuerySetT[T]":
        """Narrow the queryset."""
        raise NotImplementedError

    def values(self, *fields: str) -> "AsyncValuesQuerySetT[T]":
        """Project rows onto the given columns (dict rows)."""
        raise NotImplementedError


class AsyncValuesQuerySetT[T: Model](Protocol):
    """Projected queryset returned by :meth:`AsyncQuerySetT.values`."""

    def aget(self, **kwargs: Any) -> Awaitable[dict[str, Any]]:
        """Return exactly one projected row or raise ``DoesNotExist``."""
        raise NotImplementedError


class AsyncManagerT[T: Model](Protocol):
    """Subset of ``django_async_backend.db.models.manager.AsyncManager`` used here."""

    def aget(self, **kwargs: Any) -> Awaitable[T]:
        """Return exactly one row or raise ``DoesNotExist``."""
        raise NotImplementedError

    def acreate(self, **kwargs: Any) -> Awaitable[T]:
        """Insert a row and return the instance."""
        raise NotImplementedError

    def filter(self, **kwargs: Any) -> AsyncQuerySetT[T]:
        """Return a filtered async queryset."""
        raise NotImplementedError

    def only(self, *fields: str) -> AsyncQuerySetT[T]:
        """Return an async queryset with deferred columns."""
        raise NotImplementedError


def async_manager[T: Model](model: type[T]) -> AsyncManagerT[T]:
    """Return ``model.async_objects`` -- the async-connection manager for ``model``."""

    return model.async_objects  # type: ignore[attr-defined,no-any-return]
