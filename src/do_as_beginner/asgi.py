#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os

from .base import AppConfig
from .base.config.constants import APP_NAME
from .cli.command import group
from .server import PluginCore


def set_environment() -> None:
    """Set environment variables."""

    config = AppConfig.load()

    os.environ.setdefault("DAB_SERVER_NAME", APP_NAME.lower())
    os.environ.setdefault("DAB_SERVER_HOST", config.server.host)
    os.environ.setdefault("DAB_SERVER_PORT", str(config.server.port))
    os.environ.setdefault("DAB_SERVER_ENVIRONMENT", config.server.environment)
    os.environ.setdefault("DAB_SERVER_DEBUG", str(config.server.debug).lower())
    os.environ.setdefault("DAB_SERVER_LOG_LEVEL", config.server.log_level.lower())


def entrypoint() -> None:
    """Run administrative tasks."""

    # Set environment variables
    set_environment()

    # Setup all plugins
    PluginCore().setup()

    # Register plugins' cli commands
    for typer in PluginCore().typers:
        group.add_typer(typer)

    # Execute the commands.
    group()


if __name__ == "__main__":
    entrypoint()
