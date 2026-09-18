"""Unit tests for the plugin registry (duplicate-name check + iteration)."""

from typing import Any

import pytest

from do_as_beginner.base import AppConfig
from do_as_beginner.server.plugin import (
    AppPluginProtocol,
    CLIPluginProtocol,
    DuplicatePluginError,
    PluginProtocol,
    PluginRegistry,
)
from do_as_beginner.server.plugin.utils import discover_plugins


class FakePlugin(AppPluginProtocol):
    """Duck-typed via inheritance; name defaults to the class name."""

    def __init__(self, log: list[str], name: str | None = None) -> None:

        self.log = log
        if name is not None:
            self.name = name

    def on_app_init(self, container: Any) -> None:

        self.log.append("on_app_init")


class CliPlugin(CLIPluginProtocol):
    name = "cli"

    def __init__(self, log: list[str]) -> None:

        self.log = log

    def on_cli_init(self, group: Any) -> None:

        self.log.append("on_cli_init")


def test_duplicate_plugin_name_fails_eagerly() -> None:

    with pytest.raises(DuplicatePluginError, match="'Dup'"):
        PluginRegistry(FakePlugin([], name="Dup"), FakePlugin([], name="Dup"))


def test_plugin_name_defaults_to_class_name() -> None:

    registry = PluginRegistry(FakePlugin([]))

    assert registry.plugins[0].__class__.__name__ == "FakePlugin"


def test_plugins_preserve_registration_order_and_iterate() -> None:

    log: list[str] = []
    server = FakePlugin(log)
    cli = CliPlugin(log)

    registry = PluginRegistry(server, cli)

    assert registry.plugins == (server, cli)
    assert list(registry) == [server, cli]


def test_discover_plugins_finds_builtins_and_excludes_protocols() -> None:
    """Discovery walks protocol ``__subclasses__()``; protocol classes are never instantiated."""

    protocols = {PluginProtocol, AppPluginProtocol, CLIPluginProtocol}

    plugins = discover_plugins(AppConfig.load())
    names = {type(plugin).__name__ for plugin in plugins}

    assert {"BlobsPlugin", "OtelPlugin", "QdrantPlugin", "RedisPlugin"} <= names
    assert all(type(plugin) not in protocols for plugin in plugins)
