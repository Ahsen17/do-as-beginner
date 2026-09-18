"""Unit tests for AppConfigCore composition-root behaviour."""

from contextlib import asynccontextmanager
from typing import Any

import django
import pytest

import do_as_beginner.server.setup as core_module
from do_as_beginner.server.core import AppPluginProtocol, CLIPluginProtocol, PluginSetupError
from do_as_beginner.server.setup import AppConfigCore


@pytest.fixture
def _reset_process_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate the module-level adoption state per test."""

    monkeypatch.setattr(AppConfigCore, "_assembled", None)


class FakeSettings:
    """Stand-in for django.conf.settings so the full pipeline can run in-process."""

    configured = False

    def configure(self, **kwargs: Any) -> None:

        self.configured_kwargs = kwargs


class CoreFakeServerPlugin(AppPluginProtocol):
    """Records on_app_init; unique name to avoid registry collisions across modules."""

    name = "core-fake-server"

    def __init__(self) -> None:

        self.calls: list[Any] = []

    def on_app_init(self, container: Any) -> None:

        self.calls.append(container)


class CoreFakeCliPlugin(CLIPluginProtocol):
    name = "core-fake-cli"

    def __init__(self) -> None:

        self.calls: list[Any] = []

    def on_cli_init(self, group: Any) -> None:

        self.calls.append(group)


class CoreFakeBrokenPlugin(AppPluginProtocol):
    name = "core-fake-broken"

    def on_app_init(self, container: Any) -> None:

        raise RuntimeError("boom")


def _make_core(monkeypatch: pytest.MonkeyPatch, *plugins: Any, container: Any = None) -> AppConfigCore:

    monkeypatch.setattr(core_module, "settings", FakeSettings())
    monkeypatch.setattr(django, "setup", lambda: None)
    return AppConfigCore(*plugins, container=container)


@pytest.mark.usefixtures("_reset_process_state")
def test_setup_is_idempotent_in_configured_process() -> None:
    """Under the pytest bootstrap Django is already configured: the run short-circuits."""

    core = AppConfigCore()
    core.setup()
    core.setup()  # second call must be a no-op

    assert core.assembly is None


@pytest.mark.usefixtures("_reset_process_state")
def test_plugins_register_explicitly_in_order() -> None:
    """v3 registration: plugins enter the registry exactly as passed to the constructor."""

    first = CoreFakeServerPlugin()
    second = CoreFakeCliPlugin()
    core = AppConfigCore(first, second)

    assert core._plugin_registry.plugins == (first, second)


@pytest.mark.usefixtures("_reset_process_state")
def test_full_setup_pipeline_calls_hooks_and_collects_lifespan(monkeypatch: pytest.MonkeyPatch) -> None:

    class LifespanPlugin(AppPluginProtocol):
        name = "core-fake-lifespan"

        def on_app_init(self, container: Any) -> None:

            pass

        @asynccontextmanager
        async def __lifespan__(self) -> Any:

            yield

    server = CoreFakeServerPlugin()
    cli = CoreFakeCliPlugin()
    lifespan_plugin = LifespanPlugin()
    core = _make_core(monkeypatch, server, cli, lifespan_plugin)

    core.setup()

    assert server.calls == [core._container]  # plugins receive the DI container
    assert cli.calls == [core._cli_group]  # CLI plugins receive the root Typer group
    assert core.assembly and core.assembly.lifespans == [lifespan_plugin.__lifespan__]  # __lifespan__ collected


@pytest.mark.usefixtures("_reset_process_state")
def test_setup_failure_wraps_in_plugin_setup_error(monkeypatch: pytest.MonkeyPatch) -> None:

    broken = CoreFakeBrokenPlugin()
    core = _make_core(monkeypatch, broken)

    with pytest.raises(PluginSetupError, match="boom") as excinfo:
        core.setup()

    assert isinstance(excinfo.value.__cause__, RuntimeError)


@pytest.mark.usefixtures("_reset_process_state")
def test_adopt_assembled_shares_state(monkeypatch: pytest.MonkeyPatch) -> None:

    previous = AppConfigCore()
    monkeypatch.setattr(AppConfigCore, "_assembled", previous)

    current = AppConfigCore()
    current.setup()

    assert current._config is previous._config
    assert current._plugin_registry is previous._plugin_registry
    assert current._assembly is previous._assembly
    assert current._container is previous._container


@pytest.mark.usefixtures("_reset_process_state")
def test_django_configure_receives_merged_manifest(monkeypatch: pytest.MonkeyPatch) -> None:

    fake_settings = FakeSettings()
    monkeypatch.setattr(core_module, "settings", fake_settings)
    monkeypatch.setattr(django, "setup", lambda: None)
    core = AppConfigCore()

    core.setup()

    manifest = fake_settings.configured_kwargs
    assert manifest["INSTALLED_APPS"]
    assert "CELERY_BROKER_URL" in manifest  # CELERY_* keys enter configure for all entries
