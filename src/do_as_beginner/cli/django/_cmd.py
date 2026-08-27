from typing import Annotated

from typer import Argument

Args = Annotated[
    list[str] | None,
    Argument(help="Arguments passed to the underlying Django command"),
]

CONTEXT_SETTINGS = {
    "ignore_unknown_options": True,
    "allow_interspersed_args": False,
}


def _django_command(*args: str) -> None:

    try:
        from django.core.management import execute_from_command_line  # noqa: PLC0415

    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    execute_from_command_line(["", *args])
