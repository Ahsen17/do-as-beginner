"""Pytest bootstrap: configure a minimal Django environment for task tests.

The repo configures Django programmatically (no settings module), so tests
that import ``do_as_beginner.tasks`` models need a configured app registry
plus a SQLite database with the ``dab_tasks`` schema.
"""

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from django.conf import settings

_DB_DIR = Path(tempfile.mkdtemp(prefix="dab_test_"))
_DB_PATH = _DB_DIR / "db.sqlite3"

if not settings.configured:
    settings.configure(
        SECRET_KEY="test-secret",
        DEBUG=True,
        INSTALLED_APPS=["do_as_beginner.tasks"],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(_DB_PATH),
            }
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
        TIME_ZONE="UTC",
    )

import django
from django.core.management import call_command

django.setup()


@pytest.fixture(scope="session", autouse=True)
def _migrated_db() -> Iterator[None]:
    """Create the dab_tasks schema once for the session."""

    call_command("migrate", verbosity=0, interactive=False)
    yield
    shutil.rmtree(_DB_DIR, ignore_errors=True)
