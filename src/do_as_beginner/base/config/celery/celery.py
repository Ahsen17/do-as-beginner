from pydantic import Field

from do_as_beginner.base.schemas import BaseStruct

__all__ = (
    "CeleryConfig",
    "WorkerConcurrency",
)


class WorkerConcurrency(BaseStruct):
    """Per-tier worker concurrency quotas (the fairness floor)."""

    urgent: int = 4
    high: int = 2
    default: int = 1
    low: int = 1


class CeleryConfig(BaseStruct):
    """Configuration for the dab Celery + RabbitMQ integration."""

    broker_dsn: str = "amqp://guest:guest@localhost:5672//"
    timezone: str = "UTC"
    worker_concurrency: WorkerConcurrency = Field(default_factory=WorkerConcurrency)
    queue_prefix: str = "dab.tasks"
    delivery_limit: int = 5
    dlq_redelivery_budget: int = 2
    redelivery_backoff: list[int] = Field(default_factory=lambda: [30, 300])
    dead_letter_webhook: str | None = None
    webhook_timeout: float = Field(default=5.0, gt=0)

    def validate_redelivery(self) -> None:
        """Ensure the redelivery budget is coverable by the backoff ladder."""

        if len(self.redelivery_backoff) < self.dlq_redelivery_budget:
            raise ValueError("celery.redelivery_backoff must have at least celery.dlq_redelivery_budget entries")
