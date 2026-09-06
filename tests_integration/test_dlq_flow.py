"""Integration: trace persistence + live DLQ drain against a real broker."""

import json
import os
import uuid

import pytest
from django.conf import settings
from kombu import Connection

from do_as_beginner.tasks.handlers import DeadLetterHandler
from do_as_beginner.tasks.models import DelayedRedelivery, TaskTrace

AMQP_DSN = os.environ.get("DAB_AMQP_DSN", "amqp://dab:dab@127.0.0.1:5672/dab")
PREFIX = os.environ.get("DAB_QUEUE_PREFIX", "dab.tasks")


@pytest.fixture(autouse=True)
def _point_broker_at_env():
    """Make framework code (drain) use the env-provided broker DSN."""

    settings.CELERY_BROKER_URL = AMQP_DSN
    yield
    DelayedRedelivery.objects.all().delete()
    TaskTrace.objects.all().delete()


def test_trace_roundtrip() -> None:
    """A trace row written via the testing (SQLite) alias round-trips."""

    task_id = str(uuid.uuid4())
    TaskTrace.objects.create(task_id=task_id, task_name="t.integration", tier="default", state="enqueued")
    row = TaskTrace.objects.get(task_id=task_id)
    assert row.task_name == "t.integration"
    assert row.state == "enqueued"


def test_dlq_drain_schedules_redelivery() -> None:
    """A seeded dead letter is drained into a pending DelayedRedelivery."""

    task_id = str(uuid.uuid4())
    body = json.dumps([[], {}, {"callbacks": None, "errbacks": None, "chain": None, "chord": None}])
    headers = {
        "task": "dab.demo.boom",
        "id": task_id,
        "x-death": [{"queue": f"{PREFIX}.default"}],
    }

    with Connection(AMQP_DSN) as conn:
        producer = conn.Producer()
        producer.publish(
            body,
            exchange="",
            routing_key=f"{PREFIX}.dlq",
            headers=headers,
            content_type="application/json",
            delivery_mode=2,
        )

    processed = DeadLetterHandler().drain()
    assert processed >= 1

    row = DelayedRedelivery.objects.filter(task_id=task_id).first()
    assert row is not None
    assert row.state == "pending"
    assert row.tier == "default"
    assert row.attempt_no == 1
