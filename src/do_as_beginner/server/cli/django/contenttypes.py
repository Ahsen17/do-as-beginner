from typer import Typer

from ._cmd import CONTEXT_SETTINGS, Args, _django_command

ctt_group = Typer(
    name="contenttypes",
    help="Manage Django content types",
)


@ctt_group.command(
    name="remove_stale_content_types",
    help="Remove stale Django content types",
    context_settings=CONTEXT_SETTINGS,
)
def remove_stale_content_types(args: Args = None) -> None:

    _django_command("remove_stale_contenttypes", *(args or ()))
