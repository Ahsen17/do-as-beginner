#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os

from django.core.handlers.asgi import ASGIHandler

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
    os.environ.setdefault("DAB_SERVER_WORKERS", str(config.server.workers))


def create_application() -> ASGIHandler:

    # Set environment variables
    set_environment()

    # Setup all plugins
    PluginCore().setup()

    try:
        from django.core.asgi import get_asgi_application  # noqa: PLC0415

    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    return get_asgi_application()


def entrypoint() -> None:
    """Run administrative tasks."""

    # Set environment variables
    set_environment()

    # Setup all plugins
    PluginCore().setup()

    # Register plugins' cli commands
    for typer in PluginCore.typers:
        group.add_typer(typer)

    # Execute the commands.
    group()


if __name__ == "__main__":
    entrypoint()
