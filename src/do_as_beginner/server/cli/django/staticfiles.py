from typer import Typer

from ._cmd import CONTEXT_SETTINGS, Args, _django_command

stf_group = Typer(
    name="staticfiles",
    help="Manage Django static files",
)


@stf_group.command(
    name="collect",
    help="Collect static files",
    context_settings=CONTEXT_SETTINGS,
)
def collect(args: Args = None) -> None:

    _django_command("collectstatic", *(args or ()))


@stf_group.command(
    name="find",
    help="Find static files",
    context_settings=CONTEXT_SETTINGS,
)
def find(args: Args = None) -> None:

    _django_command("findstatic", *(args or ()))


@stf_group.command(
    name="runserver",
    help="Run the Django development server",
    context_settings=CONTEXT_SETTINGS,
)
def runserver(args: Args = None) -> None:

    _django_command("runserver", *(args or ()))
