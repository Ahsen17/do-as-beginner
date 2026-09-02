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
    """A Celery task that can be retried on failure."""

    abstract = True

    autoretry_for = (
        ConnectionError,
        TimeoutError,
    )

    max_retries = 2
    retry_backoff: int = 5  # seconds
    retry_backoff_max: int = 300
    retry_jitter: bool = True

    acks_late: bool = True
    reject_on_woker_lost: bool = True
