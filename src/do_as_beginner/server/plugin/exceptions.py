"""Exceptions raised by the plugin system."""

from do_as_beginner.shared import ApplicationError

__all__ = (
    "ContributionConflictError",
    "DuplicatePluginError",
    "PluginSetupError",
)


class DuplicatePluginError(ApplicationError):
    """Two plugins with the same :attr:`~do_as_beginner.server.plugins.ServerPlugin.name` were registered."""


class ContributionConflictError(ApplicationError):
    """Two plugins contributed the same resource (settings key, CLI name, beat entry)."""


class PluginSetupError(ApplicationError):
    """A plugin raised during its ``setup()``; the original error is chained as ``__cause__``."""
