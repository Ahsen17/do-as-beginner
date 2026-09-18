#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys

from django.apps import apps

from .base import AppConfig
from .base.config.constants import APP_NAME
from .server import AppConfigCore, LifespanWrapper
from .server.cli.command import group


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


def create_application() -> LifespanWrapper:

    # Set environment variables
    set_environment()

    core = AppConfigCore()
    core.setup()

    try:
        from django.core.asgi import get_asgi_application  # noqa: PLC0415

    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # Wrap Django's ASGIHandler with the lifespan protocol: plugin-contributed
    # resource lifetimes and the composition root's shutdown pipeline hang off
    # lifespan.startup/shutdown (Django itself does not handle them).
    lifespans = core.assembly.lifespans if core.assembly is not None else []
    return LifespanWrapper(get_asgi_application(), lifespans)


def celery_entrypoint() -> None:

    # Set environment variables
    set_environment()

    core = AppConfigCore()
    core.setup()

    if not apps.ready:
        import django  # noqa: PLC0415

        django.setup()

    # Import lazily: Django apps are ready. ``celery_app()`` is the process-wide
    # singleton also used by TaskHandler.dispatch, so worker and producer share
    # one configured app instead of building a fresh instance each.
    from .tasks.decorators import celery_app  # noqa: PLC0415

    cl = celery_app()
    cl.autodiscover_tasks()

    from .tasks.scheduler import Scheduler  # noqa: PLC0415

    argv = Scheduler.apply_worker_concurrency(list(sys.argv[1:]), AppConfig.load().celery)
    scheduler = Scheduler()
    plugin_beat = core.assembly.celery_beat_schedule if core.assembly is not None else {}

    scheduler.bootstrap(cl, plugin_beat_schedule=plugin_beat)

    cl.start(argv=argv)


def entrypoint() -> None:
    """Run administrative tasks."""

    # Set environment variables
    set_environment()

    # Assemble the server (Django settings, plugins; CLIPlugin facets inject
    # their commands onto the root group during setup).
    core = AppConfigCore()
    core.setup()

    # Execute the commands.
    group()


if __name__ == "__main__":
    entrypoint()
