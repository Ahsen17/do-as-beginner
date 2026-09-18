"""Unit tests for the plugin assembly context (no cross-plugin conflict tracking)."""

from contextlib import contextmanager
from typing import Any

import pytest

from do_as_beginner.server.core import AssemblyContext, ContributionConflictError
from do_as_beginner.server.core.constants import RESERVED_SETTING_KEYS


def test_add_installed_app_dedupes_keeping_order() -> None:

    assembly = AssemblyContext()

    assembly.add_installed_app("app_b")
    assembly.add_installed_app("app_a")
    assembly.add_installed_app("app_b")

    assert assembly.installed_apps == ["app_b", "app_a"]


def test_add_middleware_preserves_duplicates() -> None:

    assembly = AssemblyContext()

    assembly.add_middleware("mw.A")
    assembly.add_middleware("mw.A")

    assert assembly.middlewares == ["mw.A", "mw.A"]


def test_add_setting_rejects_lowercase_key() -> None:

    assembly = AssemblyContext()

    with pytest.raises(ValueError, match="all-uppercase"):
        assembly.add_setting("not_upper", 1)


@pytest.mark.parametrize("key", sorted(RESERVED_SETTING_KEYS)[:3])
def test_add_setting_rejects_reserved_keys(key: str) -> None:

    assembly = AssemblyContext()

    with pytest.raises(ContributionConflictError, match="framework-reserved"):
        assembly.add_setting(key, 1)


def test_add_setting_later_write_overwrites_earlier() -> None:
    """Litestar semantics: registration order is precedence order, no conflict error."""

    assembly = AssemblyContext()

    assembly.add_setting("CUSTOM_SETTING", 1)
    assembly.add_setting("CUSTOM_SETTING", 2)

    assert assembly.extra_settings["CUSTOM_SETTING"] == 2


def test_add_celery_task_module_dedupes() -> None:

    assembly = AssemblyContext()

    assembly.add_celery_task_module("app_a.tasks")
    assembly.add_celery_task_module("app_a.tasks")

    assert assembly.celery_task_modules == ["app_a.tasks"]


def test_add_beat_entry_later_write_overwrites_earlier() -> None:
    """Plugin-entry collisions resolve by order here; only code-declared entries
    are guarded, at ``Scheduler.bootstrap`` merge time."""

    assembly = AssemblyContext()

    assembly.add_beat_entry("tick", {"task": "t", "schedule": 1.0})
    assembly.add_beat_entry("tick", {"task": "t2", "schedule": 2.0})

    assert assembly.celery_beat_schedule["tick"] == {"task": "t2", "schedule": 2.0}


def test_add_lifespan_appends_in_order() -> None:

    assembly = AssemblyContext()

    @contextmanager
    def factory_a() -> Any:

        yield

    @contextmanager
    def factory_b() -> Any:

        yield

    assembly.add_lifespan(factory_a)
    assembly.add_lifespan(factory_b)

    assert assembly.lifespans == [factory_a, factory_b]
