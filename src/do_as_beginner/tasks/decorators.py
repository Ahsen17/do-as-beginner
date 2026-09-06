"""Task declaration decorators and the shared Celery app factory.

Kept intentionally small: ``task``/``periodic_task`` register a callable and
record its default tier, so the class-based handlers stay free of declaration
machinery.
"""

import logging
from collections.abc import Callable
from functools import cache
from typing import Any, TypeVar

from celery import Celery, Task, shared_task

from do_as_beginner.base.config.constants import APP_NAME

from .enums import QueueTier, TaskPriority, tier_of
from .task import RetriableTask

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

#: default tier declared per task name (filled by ``task``/``periodic_task``)
DECLARED_TIERS: dict[str, QueueTier] = {}

#: periodic schedule entries declared via ``periodic_task``
PERIODIC_ENTRIES: list[dict[str, Any]] = []


@cache
def celery_app() -> Celery:
    """Return the process-wide Celery app, configured once from Django settings.

    A single long-lived instance shared by the ASGI producer, the worker
    entrypoint and due-redelivery dispatch, instead of one per ``send_task``.
    """

    app = Celery(APP_NAME)
    app.config_from_object("django.conf:settings", namespace="CELERY")
    return app


def resolve_tier(name: str, tier: QueueTier | str | None = None, priority: TaskPriority | None = None) -> QueueTier:
    """Resolve the effective tier: explicit > priority > declared > ``default``."""

    if tier is not None:
        return tier if isinstance(tier, QueueTier) else QueueTier(str(tier))
    if priority is not None:
        return tier_of(priority)
    return DECLARED_TIERS.get(name, QueueTier.DEFAULT)


def task(
    *,
    name: str | None = None,
    base: type[Task] = RetriableTask,
    priority: TaskPriority = TaskPriority.DEFAULT,
    **opts: Any,
) -> Callable[[F], Any]:
    """Declare a Celery task with a default priority tier.

    Use ``base=RetriableTask`` to inherit the framework's autoretry policy.
    """

    def decorator(fn: F) -> Any:
        celery_opts: dict[str, Any] = dict(opts)
        celery_opts["base"] = base
        bound = shared_task(name=name, **celery_opts)(fn)
        key = name if name is not None else str(bound.name)
        DECLARED_TIERS[key] = tier_of(priority)
        return bound

    return decorator


def periodic_task(
    *,
    name: str,
    crontab: str | None = None,
    interval: int | None = None,
    tier: QueueTier = QueueTier.DEFAULT,
    args: tuple = (),
    kwargs: dict[str, Any] | None = None,
    **opts: Any,
) -> Callable[[F], Any]:
    """Declare a cron/interval periodic task (code-declared schedule).

    ``crontab`` is a 5-field cron expression evaluated in the configured
    (UTC) timezone; provide exactly one of ``crontab`` or ``interval``.
    """

    if (crontab is None) == (interval is None):
        raise ValueError("exactly one of crontab or interval is required")

    def decorator(fn: F) -> Any:
        bound = shared_task(name=name, **opts)(fn)
        DECLARED_TIERS.setdefault(name, tier)
        PERIODIC_ENTRIES.append(
            {
                "name": name,
                "crontab": crontab,
                "interval": interval,
                "tier": tier,
                "args": tuple(args),
                "kwargs": dict(kwargs or {}),
            }
        )
        return bound

    return decorator
