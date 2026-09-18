"""Unit tests for Scheduler.bootstrap beat merge with plugin contributions."""

from collections.abc import Callable
from typing import Any

import pytest
from django.conf import settings

from do_as_beginner.server.core import ContributionConflictError
from do_as_beginner.tasks.handlers import DeadLetterHandler
from do_as_beginner.tasks.scheduler import Scheduler


class FakeCeleryConf:
    """Attribute-access stand-in for the celery config object."""

    beat_schedule: dict[str, Any]


class FakeCeleryApp:
    """Records task registrations; enough surface for bootstrap."""

    def __init__(self) -> None:
        self.conf = FakeCeleryConf()
        self.registered: list[str] = []

    def task(self, name: str) -> Callable[[Any], Any]:
        def decorator(fn: Any) -> Any:
            self.registered.append(name)
            return fn

        return decorator


@pytest.fixture
def _beat_settings_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Snapshot and restore the process-global CELERY_BEAT_SCHEDULE around a test."""

    monkeypatch.setattr(settings, "CELERY_BEAT_SCHEDULE", {}, raising=False)


@pytest.mark.usefixtures("_beat_settings_guard")
def test_bootstrap_merges_plugin_entries_with_internal_ticks() -> None:
    scheduler = Scheduler()
    app = FakeCeleryApp()
    plugin_entry = {"task": "fake_app.tasks.pulse", "schedule": 5.0}

    scheduler.bootstrap(app, plugin_beat_schedule={"fake_pulse": plugin_entry})

    schedule = settings.CELERY_BEAT_SCHEDULE
    assert schedule["fake_pulse"] == plugin_entry
    # internal ticks survive the merge (previously bootstrap overwrote the whole schedule)
    assert DeadLetterHandler.DRAIN_TASK in schedule
    assert DeadLetterHandler.DISPATCH_DUE_TASK in schedule
    assert app.conf.beat_schedule is schedule


@pytest.mark.usefixtures("_beat_settings_guard")
def test_bootstrap_rejects_plugin_entry_colliding_with_internal_tick() -> None:
    scheduler = Scheduler()
    app = FakeCeleryApp()

    with pytest.raises(ContributionConflictError, match="code-declared entry"):
        scheduler.bootstrap(app, plugin_beat_schedule={DeadLetterHandler.DRAIN_TASK: {"task": "x"}})


@pytest.mark.usefixtures("_beat_settings_guard")
def test_bootstrap_without_plugins_keeps_internal_schedule_only() -> None:
    scheduler = Scheduler()
    app = FakeCeleryApp()

    scheduler.bootstrap(app)

    assert DeadLetterHandler.DRAIN_TASK in settings.CELERY_BEAT_SCHEDULE
