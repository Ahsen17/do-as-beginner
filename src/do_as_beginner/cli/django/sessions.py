from typer import Typer

from ._cmd import CONTEXT_SETTINGS, Args, _django_command

sessions_group = Typer(
    name="sessions",
    help="Manage Django sessions",
)


@sessions_group.command(
    name="clearsessions",
    help="Clear all sessions",
    context_settings=CONTEXT_SETTINGS,
)
def clear_sessions(args: Args = None) -> None:

    _django_command("clearsessions", *(args or ()))
