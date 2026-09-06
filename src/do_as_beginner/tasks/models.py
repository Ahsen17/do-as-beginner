from django.db import models

from .enums import QueueTier, TaskState

__all__ = (
    "DelayedRedelivery",
    "TaskTrace",
)

_QUEUE_CHOICES = [(t.value, t.name) for t in QueueTier]
_STATE_CHOICES = [(s.value, s.name) for s in TaskState]


class TaskTrace(models.Model):
    """Lifecycle trace of one logical Celery task run.

    A single logical run is identified by ``task_id``: autoretry, broker
    redeliveries and DLQ requeues all share the same id and accumulate onto
    the same row (idempotent ``update_or_create`` by ``task_id``).
    """

    task_id: models.CharField = models.CharField(max_length=64, unique=True)
    task_name: models.CharField = models.CharField(max_length=255, db_index=True)
    tier: models.CharField = models.CharField(
        max_length=16,
        choices=_QUEUE_CHOICES,
        default=QueueTier.DEFAULT.value,
    )
    state: models.CharField = models.CharField(
        max_length=16,
        choices=_STATE_CHOICES,
        default=TaskState.ENQUEUED.value,
        db_index=True,
    )
    attempts: models.PositiveSmallIntegerField = models.PositiveSmallIntegerField(default=1)
    last_error_type: models.CharField = models.CharField(max_length=255, blank=True, default="")
    last_error_message: models.TextField = models.TextField(blank=True, default="")
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    started_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    finished_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "dab_tasks"
        indexes = [
            models.Index(fields=["updated_at"], name="dab_trace_updated_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.task_name}[{self.task_id}] {self.state}"


class DelayedRedelivery(models.Model):
    """A scheduled (re)delivery of a dead-lettered message back to its tier.

    Written by the DLQ drainer while the message is still within its DLQ
    redelivery budget; executed by the beat scheduler once ``scheduled_at``
    is due (``FOR UPDATE SKIP LOCKED`` scan).
    """

    task_id: models.CharField = models.CharField(max_length=64, db_index=True)
    tier: models.CharField = models.CharField(
        max_length=16,
        choices=_QUEUE_CHOICES,
    )
    attempt_no: models.PositiveSmallIntegerField = models.PositiveSmallIntegerField()
    state: models.CharField = models.CharField(
        max_length=16,
        choices=[("pending", "pending"), ("sent", "sent"), ("failed", "failed")],
        default="pending",
        db_index=True,
    )
    message_body: models.JSONField = models.JSONField()
    message_headers: models.JSONField = models.JSONField()
    scheduled_at: models.DateTimeField = models.DateTimeField(db_index=True)
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    delivered_at: models.DateTimeField = models.DateTimeField(null=True, blank=True)
    last_error: models.TextField = models.TextField(blank=True, default="")

    class Meta:
        app_label = "dab_tasks"
        indexes = [
            models.Index(fields=["state", "scheduled_at"], name="dab_redeliv_scan_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"redeliver[{self.task_id}]#{self.attempt_no} {self.state}"
