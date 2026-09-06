from enum import IntEnum, StrEnum, auto

__all__ = (
    "QueueTier",
    "TaskPriority",
    "TaskState",
)


class TaskPriority(IntEnum):
    """Task priority levels"""

    LOW = auto()
    DEFAULT = auto()
    HIGH = auto()
    URGENT = auto()


class QueueTier(StrEnum):
    """Priority tiers, each backed by its own queue + worker quota."""

    URGENT = auto()
    HIGH = auto()
    DEFAULT = auto()
    LOW = auto()


class TaskState(StrEnum):
    """Lifecycle state machine of a logical task run.

    Transitions are monotonic (only forward) and written idempotently.
    ``DEAD`` is written only by the dead-letter chain after the DLQ budget is
    exhausted.
    """

    ENQUEUED = auto()
    RUNNING = auto()
    RETRYING = auto()
    SUCCESS = auto()
    FAILED = auto()
    DEAD = auto()


def queue_name(prefix: str, tier: QueueTier) -> str:
    """Return the broker queue name for a tier, e.g. ``dab.tasks.low``."""

    return f"{prefix}.{tier.value}"


def tier_of(priority: TaskPriority) -> QueueTier:
    """Map a TaskPriority to its QueueTier (names are kept aligned)."""

    return QueueTier[priority.name]
