"""Scheduler: beat schedule assembly and process bootstrapping.

Absorbs what used to be scattered ``beat``/``boot`` functions into one class:
- build the beat schedule (user ``@periodic_task`` entries + internal system
  ticks that drive :class:`DeadLetterHandler`),
- inject per-tier worker concurrency defaults from config,
- bootstrap a Celery app (register internal tasks, connect lifecycle signals,
  refresh the schedule).
"""

import logging
from typing import TYPE_CHECKING, Any

from celery.schedules import crontab
from django.conf import settings

from do_as_beginner.base import AppConfig

from . import decorators
from .enums import QueueTier, queue_name
from .handlers import DeadLetterHandler, TaskHandler

if TYPE_CHECKING:
    from do_as_beginner.base import CeleryConfig


__all__ = ("Scheduler",)


logger = logging.getLogger(__name__)

_INTERNAL_TICK_SECONDS = 5


class Scheduler:
    """Static helpers and bootstrap wiring for worker/beat processes."""

    @staticmethod
    def _parse_crontab(spec: str) -> crontab:
        """Parse a 5-field cron expression into a Celery ``crontab``."""

        fields = spec.strip().split()
        if len(fields) != 5:
            raise ValueError(f"crontab must have 5 fields (min hour dom mon dow), got {spec!r}")
        minute, hour, day_of_month, month_of_year, day_of_week = fields
        return crontab(
            minute=minute,
            hour=hour,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
            day_of_week=day_of_week,
        )

    @classmethod
    def build_beat_schedule(cls, cfg: "CeleryConfig") -> dict[str, Any]:
        """Merge user periodic tasks and internal system ticks into a schedule."""

        prefix = cfg.queue_prefix
        schedule: dict[str, Any] = {}

        for entry in decorators.PERIODIC_ENTRIES:
            name = str(entry["name"])
            tier = entry["tier"] if isinstance(entry["tier"], QueueTier) else QueueTier(entry["tier"])
            spec = entry["crontab"]
            schedule[name] = {
                "task": name,
                "schedule": cls._parse_crontab(str(spec)) if spec is not None else int(entry["interval"] or 0),
                "args": tuple(entry["args"]),
                "kwargs": dict(entry["kwargs"]),
                "options": {
                    "queue": queue_name(prefix, tier),
                    "routing_key": queue_name(prefix, tier),
                },
            }

        internal_queue = f"{prefix}.internal"
        internal_options = {"queue": internal_queue, "routing_key": internal_queue}
        schedule[DeadLetterHandler.DRAIN_TASK] = {
            "task": DeadLetterHandler.DRAIN_TASK,
            "schedule": _INTERNAL_TICK_SECONDS,
            "options": internal_options,
        }
        schedule[DeadLetterHandler.DISPATCH_DUE_TASK] = {
            "task": DeadLetterHandler.DISPATCH_DUE_TASK,
            "schedule": _INTERNAL_TICK_SECONDS,
            "options": internal_options,
        }
        return schedule

    @staticmethod
    def apply_worker_concurrency(argv: list[str], cfg: "CeleryConfig") -> list[str]:
        """Inject a default ``-c`` per-tier concurrency when absent.

        Only for ``worker`` with ``-Q``/``--queues`` targeting a dab tier queue
        and no explicit ``-c``/``--concurrency``. Handles ``-Q <name>`` and
        ``--queues=<name>`` spellings.
        """

        out = list(argv)
        if not out or out[0] != "worker":
            return out
        if any(arg in ("-c", "--concurrency") or arg.startswith("--concurrency=") for arg in out):
            return out

        queue: str | None = None
        for index, arg in enumerate(out):
            if arg in ("-Q", "--queues"):
                if index + 1 < len(out):
                    queue = out[index + 1]
                break
            if arg.startswith("--queues="):
                queue = arg.split("=", maxsplit=1)[1]
                break
        if not queue:
            return out

        first = queue.split(",")[0]
        for tier in QueueTier:
            if queue_name(cfg.queue_prefix, tier) == first:
                out.extend(["-c", str(getattr(cfg.worker_concurrency, tier.value))])
                break
        return out

    def __init__(self, tasks: TaskHandler | None = None, dead_letter: DeadLetterHandler | None = None) -> None:
        self.tasks = tasks or TaskHandler()
        self.dead_letter = dead_letter or DeadLetterHandler(self.tasks)

    def bootstrap(self, app: Any) -> None:
        """Register internal tasks, connect lifecycle signals, refresh schedule."""

        app.task(name=DeadLetterHandler.DRAIN_TASK)(self.dead_letter.drain)
        app.task(name=DeadLetterHandler.DISPATCH_DUE_TASK)(self.dead_letter.dispatch_due)
        self.tasks.connect_signals()

        cfg = AppConfig.load().celery
        schedule = self.build_beat_schedule(cfg)
        settings.CELERY_BEAT_SCHEDULE = schedule
        app.conf.beat_schedule = schedule
        logger.debug("dab task scheduler bootstrap complete")
