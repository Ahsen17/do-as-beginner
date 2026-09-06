"""Integration-test bootstrap (real RabbitMQ; ORM on the ``testing`` alias).

These tests are OPTED IN: they only run with ``DAB_INTEGRATION=1`` so the
default ``pytest tests`` (unit) suite never touches external services. Run
with the broker up:

    DAB_INTEGRATION=1 uv run pytest tests_integration

The database layout mirrors ``PluginCore.setup_databases``: ``default`` is the
real async PostgreSQL (production alias, declared for parity but never used by
these tests) and ``testing`` is the SQLite test DB. ``dab_tasks`` models are
routed to ``testing``, so integration assertions exercise the broker against
the same SQLite database the unit suite uses.

Endpoints default to localhost ``dab``/``dab`` and can be overridden via
``DAB_PG_*`` / ``DAB_AMQP_DSN`` / ``DAB_QUEUE_PREFIX`` environment vars.
"""

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import django
import pytest
from django.conf import settings
from django.core.management import call_command

_ENABLED = os.environ.get("DAB_INTEGRATION", "") == "1"

_DB_DIR = Path(tempfile.mkdtemp(prefix="dab_itest_"))


class _TestingRouter:
    """Route ``dab_tasks`` models to the ``testing`` (SQLite) alias."""

    def db_for_read(self, model, **hints):
        if model._meta.app_label == "dab_tasks":
            return "testing"
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == "dab_tasks":
            return "testing"
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == "dab_tasks":
            return db == "testing"
        return None


if not _ENABLED:
    # Skip every test module in this directory when integration is off.
    collect_ignore_glob = ["*.py"]
else:
    settings.configure(
        SECRET_KEY="integration-test",
        DEBUG=True,
        INSTALLED_APPS=["do_as_beginner.tasks"],
        DATABASES={
            "default": {
                "ENGINE": "django_async_backend.db.backends.postgresql",
                "NAME": os.environ.get("DAB_PG_DB", "dab"),
                "USER": os.environ.get("DAB_PG_USER", "dab"),
                "PASSWORD": os.environ.get("DAB_PG_PASS", "dab"),
                "HOST": os.environ.get("DAB_PG_HOST", "127.0.0.1"),
                "PORT": os.environ.get("DAB_PG_PORT", "5432"),
            },
            "testing": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(_DB_DIR / "db.sqlite3"),
            },
        },
        DATABASE_ROUTERS=[_TestingRouter()],
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
        TIME_ZONE="UTC",
    )
    django.setup()

AMQP_DSN = os.environ.get("DAB_AMQP_DSN", "amqp://dab:dab@127.0.0.1:5672/dab")
QUEUE_PREFIX = os.environ.get("DAB_QUEUE_PREFIX", "dab.tasks")


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> Iterator[None]:
    """Apply dab_tasks migrations to the testing (SQLite) DB once per session."""

    if not _ENABLED:
        yield
        return
    call_command("migrate", database="testing", verbosity=0, interactive=False)
    yield
    shutil.rmtree(_DB_DIR, ignore_errors=True)
