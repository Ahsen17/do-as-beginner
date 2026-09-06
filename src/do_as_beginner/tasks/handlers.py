"""Class-based handlers encapsulating the complete task flows.

One cohesive class per flow instead of scattered module functions:

- :class:`TaskHandler` — the whole life of one logical task run: dispatch,
  lifecycle state transitions (bound to Celery signals), DLQ terminal state,
  webhook notification and trace queries.
- :class:`DeadLetterHandler` — the dead-letter recovery flow: drain the DLQ,
  honour the redelivery budget/backoff, and republish due redeliveries.

Model writes are synchronous ORM (safe in the prefork worker and in a plain
producer process); Celery signal handlers are best-effort and never propagate.
"""

import json
import logging
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any

from asgiref.sync import sync_to_async
from celery import signals
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from kombu import Connection

from do_as_beginner.base import AppConfig

from . import decorators
from .enums import QueueTier, TaskPriority, TaskState, queue_name
from .models import DelayedRedelivery, TaskTrace

__all__ = (
    "DeadLetterHandler",
    "TaskHandler",
)


logger = logging.getLogger(__name__)

_DEAD_LETTER_EVENT = "task.dead_letter"
_BUDGET_EXCEEDED = "redelivery_budget_exceeded"


def _jsonable(value: Any) -> Any:
    """Recursively convert a value into a JSON-serializable shape.

    Broker headers (``x-death``) carry ``datetime``/``date`` values that a
    PostgreSQL ``jsonb`` column cannot store directly.
    """

    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


class TaskHandler:
    """Controls the full lifecycle of a single logical task run."""

    def __init__(self) -> None:
        self._connected = False

    # ------------------------------------------------------------------ #
    # dispatch
    # ------------------------------------------------------------------ #
    @staticmethod
    def _coerce_name(name_or_task: Any) -> str:
        """Accept a task name string or a bound Celery task."""

        if isinstance(name_or_task, str):
            return name_or_task
        task_name = getattr(name_or_task, "name", None)
        if not task_name:
            raise TypeError("expected a task name string or a bound Celery task")
        return str(task_name)

    def dispatch(
        self,
        name_or_task: Any,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        *,
        tier: QueueTier | str | None = None,
        priority: TaskPriority | None = None,
        **opts: Any,
    ) -> str:
        """Publish to the resolved tier queue and record the enqueued row.

        ``args``/``kwargs`` are the task's own call arguments (the worker runs
        ``task(*args, **kwargs)``) and must be JSON-serializable. ``tier`` or
        ``priority`` select the queue; ``**opts`` passes through to Celery's
        ``send_task`` (e.g. ``countdown``, ``eta``, ``expires``, ``headers``).
        ``queue``/``routing_key`` are managed by the framework (reserved).
        """

        name = self._coerce_name(name_or_task)
        resolved = decorators.resolve_tier(name, tier=tier, priority=priority)
        queue = queue_name(AppConfig.load().celery.queue_prefix, resolved)
        result = decorators.celery_app().send_task(
            name,
            args=tuple(args),
            kwargs=dict(kwargs or {}),
            queue=queue,
            routing_key=queue,
            **opts,
        )
        task_id = str(result.id)
        self.record_initial(task_id=task_id, task_name=name, tier=resolved)
        return task_id

    async def adispatch(
        self,
        name_or_task: Any,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        *,
        tier: QueueTier | str | None = None,
        priority: TaskPriority | None = None,
        **opts: Any,
    ) -> str:
        """Async variant of :meth:`dispatch` for ASGI producers."""

        name = self._coerce_name(name_or_task)
        resolved = decorators.resolve_tier(name, tier=tier, priority=priority)
        queue = queue_name(AppConfig.load().celery.queue_prefix, resolved)
        result = decorators.celery_app().send_task(
            name,
            args=tuple(args),
            kwargs=dict(kwargs or {}),
            queue=queue,
            routing_key=queue,
            **opts,
        )
        task_id = str(result.id)
        await sync_to_async(self.record_initial)(
            task_id=task_id,
            task_name=name,
            tier=resolved,
        )
        return task_id

    # ------------------------------------------------------------------ #
    # trace persistence (idempotent by task_id; terminal states are frozen)
    # ------------------------------------------------------------------ #
    def _row_or_create(self, task_id: str, task_name: str, tier: QueueTier) -> Any:
        """Fetch the trace row, creating an enqueued row if absent.

        ``get_or_create`` is atomic on the unique ``task_id``, so the worker's
        prerun write can race the producer's enqueued write safely.
        """

        row, _ = TaskTrace.objects.get_or_create(
            task_id=task_id,
            defaults={
                "task_name": task_name,
                "tier": tier.value,
                "state": TaskState.ENQUEUED.value,
                "attempts": 0,
            },
        )
        return row

    @staticmethod
    def _frozen(row: Any, target: str) -> bool:
        """Whether the current row blocks an update to ``target``."""

        current = row.state
        if current == TaskState.DEAD.value:
            return True
        if current == TaskState.SUCCESS.value:
            return target != TaskState.SUCCESS.value
        return False

    def record_initial(self, task_id: str, task_name: str, tier: QueueTier) -> None:
        """Ensure an enqueued row exists (dispatch)."""

        self._row_or_create(task_id, task_name, tier)

    def record_running(self, task_id: str, task_name: str, tier: QueueTier) -> None:
        """Record a run start (worker prerun); increments attempts."""

        row = self._row_or_create(task_id, task_name, tier)
        if self._frozen(row, TaskState.RUNNING.value):
            return
        now = timezone.now()
        row.state = TaskState.RUNNING.value
        row.attempts = int(row.attempts or 0) + 1
        row.started_at = now
        row.updated_at = now
        row.save()

    def record_retry(
        self,
        task_id: str,
        task_name: str,
        tier: QueueTier,
        error_type: str = "",
        error_message: str = "",
    ) -> None:
        """Record a retry (worker task_retry)."""

        row = self._row_or_create(task_id, task_name, tier)
        if self._frozen(row, TaskState.RETRYING.value):
            return
        row.state = TaskState.RETRYING.value
        row.last_error_type = error_type
        row.last_error_message = error_message
        row.updated_at = timezone.now()
        row.save()

    def record_success(self, task_id: str, task_name: str, tier: QueueTier) -> None:
        """Record success (worker task_success)."""

        row = self._row_or_create(task_id, task_name, tier)
        if self._frozen(row, TaskState.SUCCESS.value):
            return
        row.state = TaskState.SUCCESS.value
        row.finished_at = timezone.now()
        row.updated_at = timezone.now()
        row.save()

    def record_failure(
        self,
        task_id: str,
        task_name: str,
        tier: QueueTier,
        error_type: str = "",
        error_message: str = "",
    ) -> None:
        """Record failure (worker task_failure, incl. soft timeouts)."""

        row = self._row_or_create(task_id, task_name, tier)
        if self._frozen(row, TaskState.FAILED.value):
            return
        row.state = TaskState.FAILED.value
        row.last_error_type = error_type
        row.last_error_message = error_message
        row.finished_at = timezone.now()
        row.updated_at = timezone.now()
        row.save()

    def finalize_dead(self, task_id: str, task_name: str, tier: QueueTier, error_type: str, error_message: str) -> None:
        """Mark a trace dead after the DLQ budget is exhausted."""

        row = self._row_or_create(task_id, task_name, tier)
        now = timezone.now()
        row.state = TaskState.DEAD.value
        row.last_error_type = error_type
        row.last_error_message = error_message
        row.finished_at = now
        row.updated_at = now
        row.save()

    def schedule_redelivery(
        self,
        task_id: str,
        tier: QueueTier,
        attempt_no: int,
        message_body: dict,
        message_headers: dict,
        delay_seconds: int,
    ) -> None:
        """Insert a pending redelivery row for an in-budget DLQ message."""

        DelayedRedelivery.objects.create(
            task_id=task_id,
            tier=tier.value,
            attempt_no=attempt_no,
            state="pending",
            message_body=message_body,
            message_headers=message_headers,
            scheduled_at=timezone.now() + timedelta(seconds=delay_seconds),
        )

    # ------------------------------------------------------------------ #
    # queries / notification
    # ------------------------------------------------------------------ #
    def snapshot(self, task_id: str) -> dict[str, str | int | None] | None:
        """Return a JSON-serializable snapshot of a trace row."""

        row = TaskTrace.objects.filter(task_id=task_id).first()
        if row is None:
            return None
        return {
            "task_id": task_id,
            "task_name": str(row.task_name),
            "tier": str(row.tier),
            "state": str(row.state),
            "attempts": int(row.attempts or 0),
            "last_error_type": str(row.last_error_type),
            "last_error_message": str(row.last_error_message),
            "enqueued_at": _iso(row.created_at),
            "dead_at": _iso(row.finished_at),
        }

    def stale_running_ids(self, older_than_seconds: int) -> list[str]:
        """Return ids of traces stuck in ``running`` for too long (R9)."""

        cutoff = timezone.now() - timedelta(seconds=older_than_seconds)
        rows = TaskTrace.objects.filter(state=TaskState.RUNNING.value, updated_at__lt=cutoff).values_list(
            "task_id", flat=True
        )
        return [str(task_id) for task_id in list(rows)]

    def notify_dead_letter(self, task_id: str, reason: str) -> None:
        """POST a dead-letter event to the configured webhook (best effort)."""

        url = AppConfig.load().celery.dead_letter_webhook
        if not url:
            return
        snapshot = self.snapshot(task_id)
        if snapshot is None:
            logger.warning("dead-letter webhook skipped: no trace for %s", task_id)
            return

        payload = {
            "event": _DEAD_LETTER_EVENT,
            "task_id": snapshot["task_id"],
            "task_name": snapshot["task_name"],
            "tier": snapshot["tier"],
            "state": TaskState.DEAD.value,
            "attempts": snapshot["attempts"],
            "reason": reason,
            "last_error_type": snapshot["last_error_type"],
            "last_error_message": snapshot["last_error_message"],
            "enqueued_at": snapshot["enqueued_at"],
            "dead_at": snapshot["dead_at"],
        }
        request = urllib.request.Request(  # noqa: S310 - operator-configured webhook endpoint
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(request, timeout=5.0) as response:  # noqa: S310 - configured endpoint
                    status = getattr(response, "status", 0)
                    if 200 <= int(status) < 300:
                        return
                    raise urllib.error.HTTPError(url, int(status), "non-2xx", response.headers, None)
            except (urllib.error.URLError, OSError):
                logger.warning("dead-letter webhook attempt %d/3 failed", attempt)
                if attempt < 3:
                    time.sleep(attempt * 1.0)
        logger.error("dead-letter webhook exhausted retries for %s", task_id)

    # ------------------------------------------------------------------ #
    # celery lifecycle signals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _tier_from_routing_key(routing_key: Any) -> QueueTier:
        """Recover the tier from a routing key of the form ``<prefix>.<tier>``."""

        prefix = AppConfig.load().celery.queue_prefix
        raw = str(routing_key or "")
        if raw.startswith(f"{prefix}."):
            try:
                return QueueTier(raw[len(prefix) + 1 :])
            except ValueError:
                pass
        return QueueTier.DEFAULT

    def _delivery_tier(self, sender: Any) -> QueueTier:
        request = getattr(sender, "request", None)
        info = getattr(request, "delivery_info", None)
        if info is None:
            return QueueTier.DEFAULT
        routing_key = info.get("routing_key") if isinstance(info, dict) else getattr(info, "routing_key", None)
        return self._tier_from_routing_key(routing_key)

    @staticmethod
    def _task_name(sender: Any) -> str:
        return str(getattr(sender, "name", "") or "")

    @staticmethod
    def _task_id(explicit: Any, sender: Any) -> str:
        request = getattr(sender, "request", None)
        return str(explicit or getattr(request, "id", "") or "")

    def _on_prerun(self, task_id: Any = None, sender: Any = None, **_: Any) -> None:
        try:
            self.record_running(
                task_id=self._task_id(task_id, sender),
                task_name=self._task_name(sender),
                tier=self._delivery_tier(sender),
            )
        except Exception:
            logger.exception("lifecycle prerun hook failed")

    def _on_retry(self, task_id: Any = None, sender: Any = None, reason: Any = None, **_: Any) -> None:
        try:
            self.record_retry(
                task_id=self._task_id(task_id, sender),
                task_name=self._task_name(sender),
                tier=self._delivery_tier(sender),
                error_type=type(reason).__name__ if reason else "",
                error_message=str(reason or "")[:4000],
            )
        except Exception:
            logger.exception("lifecycle retry hook failed")

    def _on_success(self, task_id: Any = None, sender: Any = None, **_: Any) -> None:
        try:
            self.record_success(
                task_id=self._task_id(task_id, sender),
                task_name=self._task_name(sender),
                tier=self._delivery_tier(sender),
            )
        except Exception:
            logger.exception("lifecycle success hook failed")

    def _on_failure(self, task_id: Any = None, sender: Any = None, exception: Any = None, **_: Any) -> None:
        try:
            self.record_failure(
                task_id=self._task_id(task_id, sender),
                task_name=self._task_name(sender),
                tier=self._delivery_tier(sender),
                error_type=type(exception).__name__ if exception else "",
                error_message=str(exception or "")[:4000],
            )
        except Exception:
            logger.exception("lifecycle failure hook failed")

    def connect_signals(self) -> None:
        """Connect lifecycle signals to this handler (idempotent per handler)."""

        if self._connected:
            return
        signals.task_prerun.connect(self._on_prerun, weak=False)
        signals.task_retry.connect(self._on_retry, weak=False)
        signals.task_success.connect(self._on_success, weak=False)
        signals.task_failure.connect(self._on_failure, weak=False)
        self._connected = True


class DeadLetterHandler:
    """Runs the dead-letter recovery flow (drain + due redelivery dispatch)."""

    DRAIN_TASK = "dab.internal.drain_dlq"
    DISPATCH_DUE_TASK = "dab.internal.dispatch_due_redeliveries"

    _DRAIN_MAX_PER_TICK = 50
    _DISPATCH_MAX_PER_TICK = 200

    def __init__(self, tasks: TaskHandler | None = None) -> None:
        self.tasks = tasks or TaskHandler()

    @staticmethod
    def _tier_from_xdeath(headers: dict[str, Any], prefix: str) -> QueueTier:
        """Recover the source tier from the broker's ``x-death`` header."""

        deaths = headers.get("x-death")
        if isinstance(deaths, list) and deaths:
            source = str(deaths[-1].get("queue", "") if isinstance(deaths[-1], dict) else "")
            if source.startswith(f"{prefix}."):
                try:
                    return QueueTier(source[len(prefix) + 1 :])
                except ValueError:
                    pass
        return QueueTier.DEFAULT

    @staticmethod
    def _decode(body: Any) -> dict[str, Any]:
        """Decode a Celery message body into ``{"args", "kwargs"}``.

        Protocol v2 bodies are the JSON list ``[args, kwargs, embed]``; legacy
        dict bodies are kept as-is.
        """

        if isinstance(body, (bytes, bytearray)):
            body = bytes(body).decode("utf-8")
        if isinstance(body, str):
            body = json.loads(body)
        if isinstance(body, (list, tuple)) and len(body) >= 2:
            args = body[0] if isinstance(body[0], (list, tuple)) else (body[0],)
            kwargs = body[1] if isinstance(body[1], dict) else {}
            return {"args": tuple(args), "kwargs": dict(kwargs)}
        if isinstance(body, dict):
            return dict(body)
        raise ValueError(f"unsupported message body shape: {type(body).__name__}")

    def handle_message(self, payload: dict[str, Any], headers: dict[str, Any]) -> None:
        """Route one DLQ message to a scheduled redelivery or a dead finalize."""

        cfg = AppConfig.load().celery
        prefix = cfg.queue_prefix
        tier = self._tier_from_xdeath(headers, prefix)

        task_name = str(headers.get("task") or payload.get("task") or "")
        task_id = str(headers.get("id") or payload.get("id") or "")
        if not task_name or not task_id:
            raise ValueError("dead-lettered message missing task/id")

        attempt_no = int(DelayedRedelivery.objects.filter(task_id=task_id).count()) + 1
        if attempt_no <= cfg.dlq_redelivery_budget:
            delay = cfg.redelivery_backoff[attempt_no - 1]
            self.tasks.schedule_redelivery(
                task_id=task_id,
                tier=tier,
                attempt_no=attempt_no,
                message_body=_jsonable(payload),
                message_headers=_jsonable(headers),
                delay_seconds=int(delay),
            )
            return

        self.tasks.finalize_dead(
            task_id=task_id, task_name=task_name, tier=tier, error_type="", error_message="delivery budget exceeded"
        )
        self.tasks.notify_dead_letter(task_id=task_id, reason=_BUDGET_EXCEEDED)

    def drain(self) -> int:
        """Drain a bounded number of messages from the broker DLQ."""

        cfg = AppConfig.load().celery
        dlq_name = f"{cfg.queue_prefix}.dlq"
        broker = str(getattr(settings, "CELERY_BROKER_URL", "") or cfg.broker_dsn)

        processed = 0
        with Connection(broker) as connection:
            channel = connection.channel()
            try:
                while processed < self._DRAIN_MAX_PER_TICK:
                    message = channel.basic_get(dlq_name, no_ack=False)
                    if message is None:
                        break
                    try:
                        payload = self._decode(getattr(message, "body", b"{}"))
                        headers = dict(getattr(message, "headers", {}) or {})
                        self.handle_message(payload, headers)
                        channel.basic_ack(message.delivery_tag)
                        processed += 1
                    except ValueError:
                        logger.warning("dropping unreadable DLQ message (tag=%s)", message.delivery_tag)
                        channel.basic_ack(message.delivery_tag)
                    except Exception:
                        logger.exception("DLQ drain failed; leaving message for redelivery")
                        break
            finally:
                channel.close()
        return processed

    def dispatch_due(self) -> int:
        """Republish due pending redeliveries to their original tier queue."""

        cfg = AppConfig.load().celery
        prefix = cfg.queue_prefix
        now = timezone.now()
        sent = 0

        with transaction.atomic():
            rows = list(
                DelayedRedelivery.objects.select_for_update(skip_locked=True)
                .filter(state="pending", scheduled_at__lte=now)
                .order_by("scheduled_at")[: self._DISPATCH_MAX_PER_TICK]
            )
            for row in rows:
                try:
                    tier = QueueTier(str(row.tier))
                    queue = queue_name(prefix, tier)
                    payload = dict(row.message_body or {})
                    headers = dict(row.message_headers or {})
                    task_name = str(headers.get("task") or payload.get("task") or "")
                    task_id = str(headers.get("id") or payload.get("id") or "")
                    decorators.celery_app().send_task(
                        task_name,
                        args=tuple(payload.get("args") or ()),
                        kwargs=dict(payload.get("kwargs") or {}),
                        queue=queue,
                        routing_key=queue,
                        task_id=task_id or None,
                    )
                    row.state = "sent"
                    row.delivered_at = now
                    row.save()
                    sent += 1
                except Exception as exc:
                    row.state = "failed"
                    row.last_error = str(exc)[:4000]
                    row.save()
                    logger.exception("due redelivery dispatch failed for %s", row.task_id)
        return sent


def _iso(value: Any) -> str | None:
    """ISO-format a datetime-like value (``None`` stays ``None``)."""

    if value is None:
        return None
    return str(value.isoformat())
