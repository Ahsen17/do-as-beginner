from typing import TYPE_CHECKING, ClassVar

import django
from django.conf import settings

from do_as_beginner.base import AppConfig
from do_as_beginner.server.cli.command import group
from do_as_beginner.server.depi import DI, Container

from .core import (
    AppPluginProtocol,
    AssemblyContext,
    CLIPluginProtocol,
    PluginProtocol,
    PluginRegistry,
    PluginSetupError,
)
from .settings import CelerySettingsBuilder, SettingsBuilder

if TYPE_CHECKING:
    from typer import Typer


__all__ = ("AppConfigCore",)


class AppConfigCore:
    """Composition root for the server: discovered plugins, assembled once.

    ``setup()`` builds the settings manifest from
    the loaded ``AppConfig``, runs a single ``settings.configure()`` +
    ``django.setup()``, then calls each plugin's ``on_app_init(container)`` and
    ``on_cli_init(root_group)`` hooks and collects plugin ``__lifespan__``
    context managers for the ASGI lifespan (resource lifetimes hang there, not
    on a shutdown pipeline).

    When Django is already configured in this process, ``setup()`` *adopts* the
    composition root that performed the assembly (see :meth:`_adopt_assembled`)
    instead of reconfiguring.
    """

    _assembled: ClassVar["AppConfigCore | None"] = None

    def __init__(
        self,
        *plugins: PluginProtocol,
        container: Container | None = None,
    ) -> None:

        self._config = AppConfig.load()
        self._plugin_registry = PluginRegistry(*plugins)
        self._assembly: AssemblyContext | None = None
        self._container: Container = container or DI.get_default_container()
        self._cli_group: Typer = group

    @property
    def assembly(self) -> AssemblyContext | None:

        return self._assembly

    def setup(self) -> None:

        if settings.configured:
            self._adopt_assembled()
            return

        AppConfigCore._assembled = self

        try:
            self._assembly = AssemblyContext()

            manifest = SettingsBuilder.build(self._config, self._assembly)
            manifest.update(
                CelerySettingsBuilder.build(
                    self._config,
                    self._assembly,
                    installed_apps=manifest["INSTALLED_APPS"],
                ),
            )

            settings.configure(**manifest)
            django.setup()

            for plugin in self._plugin_registry:
                try:
                    if isinstance(plugin, AppPluginProtocol):
                        plugin.on_app_init(self._container)
                    if isinstance(plugin, CLIPluginProtocol):
                        plugin.on_cli_init(self._cli_group)
                    lifespan = getattr(plugin, "__lifespan__", None)
                    if callable(lifespan):
                        self._assembly.lifespans.append(lifespan)

                except Exception as exc:
                    raise PluginSetupError(f"Plugin setup error: {exc}") from exc

        except Exception:  # noqa: TRY203
            # TODO: log error
            raise

    def _adopt_assembled(self) -> None:
        """Share the assembled root's registry/config/assembly (no-op if none)."""

        previous = AppConfigCore._assembled
        if previous is None or previous is self:
            return
        self._config = previous._config
        self._plugin_registry = previous._plugin_registry
        self._assembly = previous._assembly
        self._container = previous._container
