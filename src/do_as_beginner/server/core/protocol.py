from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from typer import Typer

    from do_as_beginner.server.depi import Container

__all__ = (
    "AppPluginProtocol",
    "CLIPluginProtocol",
    "PluginProtocol",
)


@runtime_checkable
class PluginProtocol(Protocol):
    """Base protocol for all plugins"""


@runtime_checkable
class AppPluginProtocol(PluginProtocol, Protocol):
    """Server facet: inject plugins"""

    def on_app_init(self, container: "Container") -> None: ...


@runtime_checkable
class CLIPluginProtocol(PluginProtocol, Protocol):
    """CLI facet: inject commands into the root Typer group"""

    def on_cli_init(self, group: "Typer") -> None: ...
