import os

from typer import Typer

from .django._cmd import CONTEXT_SETTINGS, Args
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

    try:
        import uvicorn  # noqa: PLC0415

    except ImportError as exc:
        raise ImportError(
            "Couldn't import uvicorn. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # TODO: waiting refactor
    server_name = os.environ.get("DAB_SERVER_NAME", "do_as_beginner")
    host = os.environ.get("DAB_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("DAB_SERVER_PORT", "8000"))

    log_level = os.environ.get("DAB_SERVER_LOG_LEVEL", "info")
    debug = os.environ.get("DAB_SERVER_DEBUG", "true") == "true"
    workers = int(os.environ.get("DAB_SERVER_WORKERS", "1"))

    uvicorn.run(
        app=f"{server_name}.asgi:create_application",
        factory=True,
        host=host,
        port=port,
        log_level=log_level,
        workers=workers,
        loop="asyncio" if debug else "uvloop",
    )
