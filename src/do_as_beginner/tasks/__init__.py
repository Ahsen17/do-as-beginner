"""dab task-tracing Django app (label ``dab_tasks``)."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .apps import TasksConfig
from .enums import QueueTier, TaskPriority, TaskState

if TYPE_CHECKING:
    from .handlers import DeadLetterHandler, TaskHandler
    from .scheduler import Scheduler

__all__ = (
    "DeadLetterHandler",
    "QueueTier",
    "Scheduler",
    "TaskHandler",
    "TaskPriority",
    "TaskState",
    "TasksConfig",
)

#: Handler/scheduler classes transitively import ``models``, which Django must
#: not see while it is still importing app packages (``apps_ready`` is false
#: during ``apps.populate()``). Defer those imports to first attribute access.
_LAZY_ATTRS: dict[str, str] = {
    "DeadLetterHandler": "handlers",
    "TaskHandler": "handlers",
    "Scheduler": "scheduler",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_ATTRS.get(name)
    if module_name is not None:
        return getattr(import_module(f"{__name__}.{module_name}"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
