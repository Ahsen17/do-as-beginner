from typer import Typer

from ._cmd import CONTEXT_SETTINGS, Args, _django_command

auth_group = Typer(
    name="changepassword",
    help="Manage Django authentication",
)


@auth_group.command(
    name="createsuperuser",
    help="Create a superuser",
    context_settings=CONTEXT_SETTINGS,
)
def createsuperuser(args: Args = None) -> None:

    _django_command("createsuperuser", *(args or ()))


@auth_group.command(
    name="changepassword",
    help="Change superuser's password",
    context_settings=CONTEXT_SETTINGS,
)
def changepassword(args: Args = None) -> None:

    _django_command("changepassword", *(args or ()))
