"""Unit tests for AppConfigCore composition-root behaviour."""

from contextlib import asynccontextmanager
from typing import Any

import django
import pytest

import do_as_beginner.server.core.core as core_module
from do_as_beginner.base import AppConfig
from do_as_beginner.server import AppConfigCore, PluginSetupError
from do_as_beginner.server.plugin import AppPluginProtocol, CLIPluginProtocol

BUILTIN_NAMES = {"BlobsPlugin", "OtelPlugin", "QdrantPlugin", "RedisPlugin"}


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
    """Records on_app_init; unique name to avoid discovery collisions across modules."""

    name = "core-fake-server"

    def __init__(self, config: Any) -> None:

        self.config = config
        self.calls: list[Any] = []

    def on_app_init(self, container: Any) -> None:

        self.calls.append(container)


class CoreFakeCliPlugin(CLIPluginProtocol):
    name = "core-fake-cli"

    def __init__(self, config: Any) -> None:

        self.config = config
        self.calls: list[Any] = []

    def on_cli_init(self, group: Any) -> None:

        self.calls.append(group)


class CoreFakeBrokenPlugin(AppPluginProtocol):
    name = "core-fake-broken"

    def __init__(self, config: Any) -> None:

        self.config = config

    def on_app_init(self, container: Any) -> None:

        raise RuntimeError("boom")


def _make_core(monkeypatch: pytest.MonkeyPatch, *plugins: Any, container: Any = None) -> AppConfigCore:

    monkeypatch.setattr(core_module, "settings", FakeSettings())
    monkeypatch.setattr(django, "setup", lambda: None)
    monkeypatch.setattr(core_module, "discover_plugins", lambda config: list(plugins))
    return AppConfigCore(container=container)


@pytest.mark.usefixtures("_reset_process_state")
def test_setup_is_idempotent_in_configured_process() -> None:
    """Under the pytest bootstrap Django is already configured: the run short-circuits."""

    core = AppConfigCore()
    core.setup()
    core.setup()  # second call must be a no-op

    assert core.assembly is None


@pytest.mark.usefixtures("_reset_process_state")
def test_builtin_plugins_are_discovered() -> None:

    core = AppConfigCore()
    names = {type(plugin).__name__ for plugin in core._plugin_registry.plugins}

    assert BUILTIN_NAMES <= names


@pytest.mark.usefixtures("_reset_process_state")
def test_full_setup_pipeline_calls_hooks_and_collects_lifespan(monkeypatch: pytest.MonkeyPatch) -> None:

    class LifespanPlugin(AppPluginProtocol):
        name = "core-fake-lifespan"

        def __init__(self, config: Any) -> None:

            self.config = config

        def on_app_init(self, container: Any) -> None:

            pass

        @asynccontextmanager
        async def __lifespan__(self) -> Any:

            yield

    server = CoreFakeServerPlugin(AppConfig.load())
    cli = CoreFakeCliPlugin(AppConfig.load())
    lifespan_plugin = LifespanPlugin(AppConfig.load())
    core = _make_core(monkeypatch, server, cli, lifespan_plugin)

    core.setup()

    assert server.calls == [core._container]  # plugins receive the DI container
    assert cli.calls == [core._cli_group]  # CLI plugins receive the root Typer group
    assert core.assembly and core.assembly.lifespans == [lifespan_plugin.__lifespan__]  # __lifespan__ collected


@pytest.mark.usefixtures("_reset_process_state")
def test_setup_failure_wraps_in_plugin_setup_error(monkeypatch: pytest.MonkeyPatch) -> None:

    broken = CoreFakeBrokenPlugin(AppConfig.load())
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
    monkeypatch.setattr(core_module, "discover_plugins", lambda config: [])
    core = AppConfigCore()

    core.setup()

    manifest = fake_settings.configured_kwargs
    assert manifest["INSTALLED_APPS"]
    assert "CELERY_BROKER_URL" in manifest  # CELERY_* keys enter configure for all entries
