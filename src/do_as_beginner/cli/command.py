import os

from typer import Typer

from .django._cmd import CONTEXT_SETTINGS, Args, _django_command
from .django.auth import auth_group
from .django.contenttypes import ctt_group
from .django.django import django_group
from .django.sessions import sessions_group
from .django.staticfiles import stf_group

group = Typer(
    name="Do as Beginner",
    help="Do as beginner CLI",
    add_completion=False,
)

group.add_typer(auth_group, name="auth")
group.add_typer(ctt_group, name="contenttypes")
group.add_typer(sessions_group, name="sessions")
group.add_typer(stf_group, name="staticfiles")
group.add_typer(django_group, name="django")


@group.command(name="run", help="Run server", context_settings=CONTEXT_SETTINGS)
def run(args: Args = None) -> None:
    host = os.environ.get("DAB_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("DAB_SERVER_PORT", "8000"))
    environment = os.environ.get("DAB_SERVER_ENVIRONMENT", "development")

    if environment == "development":
        # Run in "development" mode

        _django_command("runserver", f"{host}:{port}", *(args or ()))

    else:
        # Run in "staging" or "production" mode

        try:
            import uvicorn  # noqa: PLC0415
            from django.core.asgi import get_asgi_application  # noqa: PLC0415

        except ImportError as exc:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            ) from exc

        # TODO: waiting refactor
        log_level = os.environ.get("DAB_SERVER_LOG_LEVEL", "info")
        debug = os.environ.get("DAB_SERVER_DEBUG", "true") == "true"

        uvicorn.run(
            get_asgi_application(),
            host=host,
            port=port,
            log_level=log_level,
            workers=1 if debug else 4,
            loop="asyncio" if debug else "uvloop",
        )
