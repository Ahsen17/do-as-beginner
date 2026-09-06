"""Unit tests for pure task-runtime logic (no broker/DB)."""

import pytest

from do_as_beginner.base.config.celery import CeleryConfig
from do_as_beginner.tasks.enums import QueueTier, TaskPriority, queue_name, tier_of
from do_as_beginner.tasks.scheduler import Scheduler


def test_tier_of_maps_every_priority() -> None:
    assert tier_of(TaskPriority.LOW) is QueueTier.LOW
    assert tier_of(TaskPriority.DEFAULT) is QueueTier.DEFAULT
    assert tier_of(TaskPriority.HIGH) is QueueTier.HIGH
    assert tier_of(TaskPriority.URGENT) is QueueTier.URGENT


def test_queue_name_builds_prefixed_names() -> None:
    assert queue_name("dab.tasks", QueueTier.URGENT) == "dab.tasks.urgent"
    assert queue_name("queue", QueueTier.LOW) == "queue.low"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["worker", "--queues=dab.tasks.urgent"], ["worker", "--queues=dab.tasks.urgent", "-c", "4"]),
        (["worker", "-Q", "dab.tasks.low"], ["worker", "-Q", "dab.tasks.low", "-c", "1"]),
        (["worker", "--queues=dab.tasks.internal"], ["worker", "--queues=dab.tasks.internal"]),
        (
            ["worker", "--queues=dab.tasks.default", "--concurrency=3"],
            ["worker", "--queues=dab.tasks.default", "--concurrency=3"],
        ),
        (["worker", "--queues=other.tier"], ["worker", "--queues=other.tier"]),
        (["beat"], ["beat"]),
    ],
)
def test_concurrency_injection(argv: list[str], expected: list[str]) -> None:
    cfg = CeleryConfig()
    assert Scheduler.apply_worker_concurrency(argv, cfg) == expected


def test_crontab_parse_accepts_five_fields() -> None:
    spec = Scheduler._parse_crontab("30 1 * * *")
    assert 30 in spec.minute
    assert 1 in spec.hour


def test_crontab_parse_rejects_wrong_field_count() -> None:
    with pytest.raises(ValueError):
        Scheduler._parse_crontab("30 1 * *")
