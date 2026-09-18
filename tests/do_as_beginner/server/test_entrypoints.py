"""Unit tests for entrypoint wiring and the subprocess end-to-end smoke."""

import subprocess
import sys
from typing import Any

import pytest

import do_as_beginner.asgi as asgi_module
from do_as_beginner.server import AppConfigCore


@pytest.fixture
def _reset_process_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate the module-level adoption state per test."""

    monkeypatch.setattr(AppConfigCore, "_assembled", None)


@pytest.mark.usefixtures("_reset_process_state")
def test_entrypoint_runs_setup_then_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """R10: entrypoint assembles once, then executes the root Typer group.

    CLIPlugin facets inject their commands during setup() itself, so the
    entrypoint only orchestrates setup -> group().
    """

    calls: list[str] = []

    class EntryPointFakeCore:
        def __init__(self, *args: Any, **kwargs: Any) -> None:

            pass

        def setup(self) -> None:

            calls.append("setup")

    class FakeGroup:
        def __call__(self) -> None:

            calls.append("group")
            raise SystemExit(0)

    monkeypatch.setattr("do_as_beginner.asgi.AppConfigCore", EntryPointFakeCore)
    monkeypatch.setattr("do_as_beginner.asgi.group", FakeGroup())

    with pytest.raises(SystemExit):
        asgi_module.entrypoint()

    assert calls == ["setup", "group"]


def test_create_application_assembles_and_wraps_lifespan(tmp_path: Any) -> None:
    """R10 end-to-end smoke (subprocess): real discovery, Django setup, lifespan wrapper."""

    code = (
        "from do_as_beginner.asgi import create_application\n"
        "from django.conf import settings\n"
        "app = create_application()\n"
        "print(type(app).__name__)\n"
        "print(settings.configured)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=120,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines()[0] == "LifespanWrapper"
    assert proc.stdout.splitlines()[1] == "True"
