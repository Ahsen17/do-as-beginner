"""Pytest bootstrap: configure a minimal Django environment for task tests.

The repo configures Django programmatically (no settings module), so tests
that import ``do_as_beginner.tasks`` models need a configured app registry
plus a SQLite database with the ``dab_tasks`` schema.
"""

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest
from django.conf import settings
from psycopg import sql

_DB_DIR = Path(tempfile.mkdtemp(prefix="dab_test_"))
_DB_PATH = _DB_DIR / "db.sqlite3"

# When DAB_TEST_PG_DSN is set (R9 integration), the default alias becomes the real
# PostgreSQL via django-async-backend so async_atomic/async-ORM paths are exercised.
_PG_DSN = os.environ.get("DAB_TEST_PG_DSN", "")

if _PG_DSN:
    _parts = urlsplit(_PG_DSN)
    _PG_DB: dict[str, object] = {
        "ENGINE": "django_async_backend.db.backends.postgresql",
        "NAME": _parts.path.lstrip("/"),
        "USER": _parts.username or "",
        "PASSWORD": _parts.password or "",
        "HOST": _parts.hostname or "",
        "PORT": _parts.port or 5432,
        "OPTIONS": {},
    }
else:
    _PG_DB = {}

if not settings.configured:
    settings.configure(
        SECRET_KEY="test-secret",
        DEBUG=True,
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django_async_backend",
            "do_as_beginner.blobs",
            "do_as_beginner.tasks",
        ],
        DATABASES={
            "default": (
                _PG_DB or {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": str(_DB_PATH),
                }
            )
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
        TIME_ZONE="UTC",
    )

import django
from django.core.management import call_command

django.setup()


def _pg_dbname() -> str:
    """Return the database named in ``DAB_TEST_PG_DSN``, refusing non-test names."""

    dbname = urlsplit(_PG_DSN).path.lstrip("/")
    if not (dbname.startswith("test_") or dbname.endswith("_test")):
        msg = (
            f"Refusing to run PG integration tests against database {dbname!r}: "
            "DAB_TEST_PG_DSN must point at a database whose name starts with 'test_' "
            "or ends with '_test' (the session may create and drop it)."
        )
        raise RuntimeError(msg)
    return dbname


def _ensure_pg_database() -> bool:
    """Create the test database when missing; return whether this session created it."""

    dbname = _pg_dbname()
    admin_dsn = _PG_DSN.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        if cur.fetchone() is None:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
            return True
    return False


def _drop_pg_database() -> None:
    """Drop the test database named in ``DAB_TEST_PG_DSN``."""

    dbname = _pg_dbname()
    admin_dsn = _PG_DSN.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname))
        )


@pytest.fixture(scope="session", autouse=True)
def _migrated_db() -> Iterator[None]:
    """Create the schemas once for the session (contenttypes, dab_blobs, dab_tasks)."""

    pg_db_created = _ensure_pg_database() if _PG_DSN else False
    call_command("migrate", verbosity=0, interactive=False)
    yield
    # Only ever drop a database this session created; a pre-existing one is left alone.
    if pg_db_created:
        _drop_pg_database()
    shutil.rmtree(_DB_DIR, ignore_errors=True)
