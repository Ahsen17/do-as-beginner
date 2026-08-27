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
    port = os.environ.get("DAB_SERVER_PORT", "8000")

    _django_command("runserver", f"{host}:{port}", *(args or ()))
