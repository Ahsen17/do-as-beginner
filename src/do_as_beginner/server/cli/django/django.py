from typer import Typer

from ._cmd import CONTEXT_SETTINGS, Args, _django_command

django_group = Typer(
    name="django",
    help="Manage Django projects",
)


@django_group.command(
    name="check",
    help="Check Django settings",
    context_settings=CONTEXT_SETTINGS,
)
def check(args: Args = None) -> None:

    _django_command("check", *(args or ()))


@django_group.command(
    name="compilemessages",
    help="Compile Django messages",
    context_settings=CONTEXT_SETTINGS,
)
def compilemessages(args: Args = None) -> None:

    _django_command("compilemessages", *(args or ()))


@django_group.command(
    name="createcachetable",
    help="Create the cache table(s)",
    context_settings=CONTEXT_SETTINGS,
)
def createcachetable(args: Args = None) -> None:

    _django_command("createcachetable", *(args or ()))


@django_group.command(
    name="dbshell",
    help="Run the command-line client for the database",
    context_settings=CONTEXT_SETTINGS,
)
def dbshell(args: Args = None) -> None:

    _django_command("dbshell", *(args or ()))


@django_group.command(
    name="diffsettings",
    help="Show differences between the current and default settings",
    context_settings=CONTEXT_SETTINGS,
)
def diffsettings(args: Args = None) -> None:

    _django_command("diffsettings", *(args or ()))


@django_group.command(
    name="dumpdata",
    help="Output the contents of the database as a fixture",
    context_settings=CONTEXT_SETTINGS,
)
def dumpdata(args: Args = None) -> None:

    _django_command("dumpdata", *(args or ()))


@django_group.command(
    name="flush",
    help="Remove all data from the database",
    context_settings=CONTEXT_SETTINGS,
)
def flush(args: Args = None) -> None:

    _django_command("flush", *(args or ()))


@django_group.command(
    name="inspectdb",
    help="Introspect database tables and output Django models",
    context_settings=CONTEXT_SETTINGS,
)
def inspectdb(args: Args = None) -> None:

    _django_command("inspectdb", *(args or ()))


@django_group.command(
    name="loaddata",
    help="Install the named fixture(s) in the database",
    context_settings=CONTEXT_SETTINGS,
)
def loaddata(args: Args = None) -> None:

    _django_command("loaddata", *(args or ()))


@django_group.command(
    name="makemessages",
    help="Extract translatable strings from the source tree",
    context_settings=CONTEXT_SETTINGS,
)
def makemessages(args: Args = None) -> None:

    _django_command("makemessages", *(args or ()))


@django_group.command(
    name="makemigrations",
    help="Create new migration(s) for apps",
    context_settings=CONTEXT_SETTINGS,
)
def makemigrations(args: Args = None) -> None:

    _django_command("makemigrations", *(args or ()))


@django_group.command(
    name="migrate",
    help="Update the database schema",
    context_settings=CONTEXT_SETTINGS,
)
def migrate(args: Args = None) -> None:

    _django_command("migrate", *(args or ()))


@django_group.command(
    name="optimizemigration",
    help="Optimize the operations for the named migration",
    context_settings=CONTEXT_SETTINGS,
)
def optimizemigration(args: Args = None) -> None:

    _django_command("optimizemigration", *(args or ()))


@django_group.command(
    name="sendtestemail",
    help="Send a test email to the specified address(es)",
    context_settings=CONTEXT_SETTINGS,
)
def sendtestemail(args: Args = None) -> None:

    _django_command("sendtestemail", *(args or ()))


@django_group.command(
    name="shell",
    help="Run a Python interactive interpreter",
    context_settings=CONTEXT_SETTINGS,
)
def shell(args: Args = None) -> None:

    _django_command("shell", *(args or ()))


@django_group.command(
    name="showmigrations",
    help="Show available migrations for the current project",
    context_settings=CONTEXT_SETTINGS,
)
def showmigrations(args: Args = None) -> None:

    _django_command("showmigrations", *(args or ()))


@django_group.command(
    name="sqlflush",
    help="Print the SQL statements required to flush the database",
    context_settings=CONTEXT_SETTINGS,
)
def sqlflush(args: Args = None) -> None:

    _django_command("sqlflush", *(args or ()))


@django_group.command(
    name="sqlmigrate",
    help="Print the SQL statements for the named migration",
    context_settings=CONTEXT_SETTINGS,
)
def sqlmigrate(args: Args = None) -> None:

    _django_command("sqlmigrate", *(args or ()))


@django_group.command(
    name="sqlsequencereset",
    help="Print the SQL statements for resetting sequences",
    context_settings=CONTEXT_SETTINGS,
)
def sqlsequencereset(args: Args = None) -> None:

    _django_command("sqlsequencereset", *(args or ()))


@django_group.command(
    name="squashmigrations",
    help="Squash an existing set of migrations into one",
    context_settings=CONTEXT_SETTINGS,
)
def squashmigrations(args: Args = None) -> None:

    _django_command("squashmigrations", *(args or ()))


@django_group.command(
    name="startapp",
    help="Create a Django app directory structure",
    context_settings=CONTEXT_SETTINGS,
)
def startapp(args: Args = None) -> None:

    _django_command("startapp", *(args or ()))


@django_group.command(
    name="startproject",
    help="Create a Django project directory structure",
    context_settings=CONTEXT_SETTINGS,
)
def startproject(args: Args = None) -> None:

    _django_command("startproject", *(args or ()))


@django_group.command(
    name="test",
    help="Run tests for all installed apps",
    context_settings=CONTEXT_SETTINGS,
)
def test(args: Args = None) -> None:

    _django_command("test", *(args or ()))


@django_group.command(
    name="testserver",
    help="Run a development server with data from fixture(s)",
    context_settings=CONTEXT_SETTINGS,
)
def testserver(args: Args = None) -> None:

    _django_command("testserver", *(args or ()))
