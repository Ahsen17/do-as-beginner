#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os

from .base import AppConfig
from .base.config.constants import APP_NAME, BASE_DIR
from .cli.command import group
from .server import PluginCore


def set_environment() -> None:
    """Set environment variables."""

    config = AppConfig.load()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"{APP_NAME}.core.settings")

    os.environ.setdefault("DAB_SERVER_NAME", APP_NAME.lower())
    os.environ.setdefault("DAB_SERVER_BASE_DIR", str(BASE_DIR))
    os.environ.setdefault("DAB_SERVER_HOST", config.server.host)
    os.environ.setdefault("DAB_SERVER_PORT", str(config.server.port))
    os.environ.setdefault("DAB_SERVER_DEBUG", str(config.server.debug).lower())
    os.environ.setdefault("DAB_SERVER_LOG_LEVEL", config.server.log_level.lower())

    os.environ.setdefault("DAB_POSTGRES_DATRABASE", config.postgres.database)
    os.environ.setdefault("DAB_POSTGRES_HOST", config.postgres.host)
    os.environ.setdefault("DAB_POSTGRES_PORT", str(config.postgres.port))
    os.environ.setdefault("DAB_POSTGRES_USERNAME", config.postgres.username)
    os.environ.setdefault("DAB_POSTGRES_PASSWORD", config.postgres.password)
    os.environ.setdefault("DAB_POSTGRES_CONN_MAX_AGE", str(config.postgres.conn_max_age))
    os.environ.setdefault("DAB_POSTGRES_POOL_ENABLED", str(config.postgres.pool_enabled).lower())
    os.environ.setdefault("DAB_POSTGRES_POOL_MIN_SIZE", str(config.postgres.pool_min_size))
    os.environ.setdefault("DAB_POSTGRES_POOL_MAX_SIZE", str(config.postgres.pool_max_size))
    os.environ.setdefault("DAB_POSTGRES_COMMAND_TIMEOUT", str(config.postgres.command_timeout))


def entrypoint() -> None:
    """Run administrative tasks."""

    # Set environment variables
    set_environment()

    # Setup all plugins
    PluginCore().setup()

    # Execute the commands.
    group()


if __name__ == "__main__":
    entrypoint()
