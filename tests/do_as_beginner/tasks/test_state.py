"""State-machine and DLQ-budget tests backed by the SQLite dab_tasks schema."""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from do_as_beginner.tasks import decorators
from do_as_beginner.tasks.enums import QueueTier, TaskPriority, TaskState
from do_as_beginner.tasks.handlers import DeadLetterHandler, TaskHandler
from do_as_beginner.tasks.models import DelayedRedelivery, TaskTrace

_TASK_ID = "test-run-1"


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    DelayedRedelivery.objects.all().delete()
    TaskTrace.objects.all().delete()
    yield


def test_dispatch_passes_through_send_opts(monkeypatch) -> None:
    """``dispatch`` forwards send_task options and records the enqueued row."""

    sent: dict[str, Any] = {}

    class _FakeApp:
        def send_task(self, name: str, **opts: object) -> SimpleNamespace:
            sent["name"] = name
            sent["opts"] = opts
            return SimpleNamespace(id="abc-123")

    monkeypatch.setattr(decorators, "celery_app", lambda: _FakeApp())

    handler = TaskHandler()
    task_id = handler.dispatch(
        "t.opts",
        args=(1,),
        kwargs={"a": 2},
        priority=TaskPriority.HIGH,
        countdown=60,
        headers={"x": "y"},
    )

    assert task_id == "abc-123"
    assert sent["name"] == "t.opts"
    opts = sent["opts"]
    assert opts["args"] == (1,)
    assert opts["kwargs"] == {"a": 2}
    assert opts["countdown"] == 60
    assert opts["headers"] == {"x": "y"}
    assert opts["queue"] == "dab.tasks.high"

    row = TaskTrace.objects.get(task_id="abc-123")
    assert row.state == TaskState.ENQUEUED.value
    assert row.tier == QueueTier.HIGH.value


def test_lifecycle_reaches_terminal_success() -> None:
    handler = TaskHandler()
    handler.record_initial(_TASK_ID, "t.demo", QueueTier.HIGH)
    handler.record_running(_TASK_ID, "t.demo", QueueTier.HIGH)
    handler.record_success(_TASK_ID, "t.demo", QueueTier.HIGH)

    row = TaskTrace.objects.get(task_id=_TASK_ID)
    assert row.state == TaskState.SUCCESS.value
    assert row.attempts == 1


def test_failure_records_error_and_is_rerunnable() -> None:
    handler = TaskHandler()
    handler.record_initial(_TASK_ID, "t.demo", QueueTier.DEFAULT)
    handler.record_failure(_TASK_ID, "t.demo", QueueTier.DEFAULT, "RuntimeError", "boom")

    row = TaskTrace.objects.get(task_id=_TASK_ID)
    assert row.state == TaskState.FAILED.value
    assert row.last_error_type == "RuntimeError"

    # A broker redelivery may run the task again after a failure.
    handler.record_running(_TASK_ID, "t.demo", QueueTier.DEFAULT)
    assert TaskTrace.objects.get(task_id=_TASK_ID).state == TaskState.RUNNING.value
    assert TaskTrace.objects.get(task_id=_TASK_ID).attempts == 1


def test_success_is_terminal_frozen() -> None:
    handler = TaskHandler()
    handler.record_initial(_TASK_ID, "t.demo", QueueTier.DEFAULT)
    handler.record_running(_TASK_ID, "t.demo", QueueTier.DEFAULT)
    handler.record_success(_TASK_ID, "t.demo", QueueTier.DEFAULT)
    handler.record_running(_TASK_ID, "t.demo", QueueTier.DEFAULT)

    assert TaskTrace.objects.get(task_id=_TASK_ID).state == TaskState.SUCCESS.value


def test_dlq_budget_schedules_then_dead() -> None:
    dead_letter = DeadLetterHandler()
    headers = {"task": "t.demo", "id": _TASK_ID, "x-death": [{"queue": "dab.tasks.urgent"}]}
    payload: dict = {}

    dead_letter.handle_message(payload, headers)  # in-budget -> attempt 1 pending
    dead_letter.handle_message(payload, headers)  # in-budget -> attempt 2 pending
    assert DelayedRedelivery.objects.filter(task_id=_TASK_ID).count() == 2

    dead_letter.handle_message(payload, headers)  # out of budget -> dead
    assert DelayedRedelivery.objects.filter(task_id=_TASK_ID).count() == 2
    trace = TaskTrace.objects.get(task_id=_TASK_ID)
    assert trace.state == TaskState.DEAD.value
    assert trace.tier == QueueTier.URGENT.value


def test_dead_is_terminal_frozen() -> None:
    handler = TaskHandler()
    handler.finalize_dead(_TASK_ID, "t.demo", QueueTier.DEFAULT, "Err", "x")
    handler.record_running(_TASK_ID, "t.demo", QueueTier.DEFAULT)

    assert TaskTrace.objects.get(task_id=_TASK_ID).state == TaskState.DEAD.value
