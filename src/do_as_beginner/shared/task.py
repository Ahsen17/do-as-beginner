from enum import IntEnum, auto

from celery import Task

__all__ = (
    "RetriableTask",
    "TaskPriority",
)


class TaskPriority(IntEnum):
    """Task priority levels"""

    LOW = auto()
    DEFAULT = auto()
    HIGH = auto()
    URGENT = auto()


class RetriableTask(Task):  # type: ignore
    """A Celery task that automatically retries transient failures.

    Delivery semantics (``acks_late``, ``reject_on_worker_lost``,
    ``acks_on_failure_or_timeout``) are configured globally in ``PluginCore``
    (single source of truth) and deliberately not duplicated here.
    """

    abstract = True

    autoretry_for = (
        ConnectionError,
        TimeoutError,
    )

    max_retries = 2
    retry_backoff: int = 5  # seconds
    retry_backoff_max: int = 300
    retry_jitter: bool = True
