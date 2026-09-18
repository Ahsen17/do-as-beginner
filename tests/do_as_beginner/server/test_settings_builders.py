"""Unit tests for the settings builders (framework manifests + plugin contributions)."""

import pytest

from do_as_beginner.base import AppConfig
from do_as_beginner.server.core import AssemblyContext, ContributionConflictError
from do_as_beginner.server.settings import CelerySettingsBuilder, SettingsBuilder


def test_settings_manifest_contains_framework_builtins() -> None:
    config = AppConfig.load()
    manifest = SettingsBuilder.build(config, AssemblyContext())

    assert manifest["INSTALLED_APPS"] == list(SettingsBuilder.BASE_APPS)
    assert manifest["MIDDLEWARE"] == list(SettingsBuilder.MIDDLEWARES)
    assert manifest["ROOT_URLCONF"] == "do_as_beginner.server.core.routes"
    assert manifest["DATABASES"]["default"]["ENGINE"] == "django_async_backend.db.backends.postgresql"
    assert manifest["DATABASES"]["testing"]["ENGINE"] == "django.db.backends.sqlite3"


def test_settings_manifest_merges_plugin_contributions() -> None:
    assembly = AssemblyContext()
    assembly.add_installed_app("fake_app")
    assembly.add_middleware("fake.middleware.Fake")
    assembly.add_setting("CUSTOM_SETTING", {"a": 1})

    manifest = SettingsBuilder.build(AppConfig.load(), assembly)

    assert manifest["INSTALLED_APPS"] == [*SettingsBuilder.BASE_APPS, "fake_app"]
    assert manifest["MIDDLEWARE"] == [*SettingsBuilder.MIDDLEWARES, "fake.middleware.Fake"]
    assert manifest["CUSTOM_SETTING"] == {"a": 1}


def test_settings_manifest_rejects_reserved_extra_settings() -> None:
    assembly = AssemblyContext()
    assembly.extra_settings["INSTALLED_APPS"] = ["hijacked"]

    with pytest.raises(ContributionConflictError, match="framework-reserved"):
        SettingsBuilder.build(AppConfig.load(), assembly)


def test_settings_manifest_dedupes_plugin_installed_apps() -> None:
    assembly = AssemblyContext()
    assembly.add_installed_app("do_as_beginner.blobs")  # already in the base set

    manifest = SettingsBuilder.build(AppConfig.load(), assembly)

    assert manifest["INSTALLED_APPS"].count("do_as_beginner.blobs") == 1


def test_celery_manifest_defaults() -> None:
    config = AppConfig.load()
    manifest = CelerySettingsBuilder.build(config, AssemblyContext(), installed_apps=[])

    assert manifest["CELERY_TASK_IGNORE_RESULT"] is True
    assert manifest["CELERY_TASK_ACKS_LATE"] is True
    assert manifest["CELERY_TASK_CREATE_MISSING_QUEUES"] is False
    # four tier queues + internal + DLQ
    assert len(manifest["CELERY_TASK_QUEUES"]) == 6
    assert manifest["CELERY_TASK_DEFAULT_EXCHANGE"] == f"{config.celery.queue_prefix}.exchange"


def test_celery_manifest_merges_task_imports_with_dedupe() -> None:
    assembly = AssemblyContext()
    assembly.add_celery_task_module("fake_app.tasks")
    assembly.add_celery_task_module("fake_app.tasks")

    manifest = CelerySettingsBuilder.build(AppConfig.load(), assembly, installed_apps=[])

    assert manifest["CELERY_IMPORTS"] == ("fake_app.tasks",)


def test_celery_manifest_does_not_set_beat_schedule() -> None:
    # beat entries are merged in Scheduler.bootstrap after task import
    manifest = CelerySettingsBuilder.build(AppConfig.load(), AssemblyContext(), installed_apps=[])

    assert "CELERY_BEAT_SCHEDULE" not in manifest


def test_django_manifest_matches_pre_refactor_values() -> None:
    """R1 acceptance: full key-by-key equivalence with the pre-refactor setup.py output."""

    config = AppConfig.load()
    manifest = SettingsBuilder.build(config, AssemblyContext())

    assert set(manifest) == {
        "SECRET_KEY",
        "DEBUG",
        "ALLOWED_HOSTS",
        "INSTALLED_APPS",
        "MIDDLEWARE",
        "ROOT_URLCONF",
        "TEMPLATES",
        "DATABASES",
        "AUTH_PASSWORD_VALIDATORS",
        "LANGUAGE_CODE",
        "TIME_ZONE",
        "USE_I18N",
        "USE_TZ",
        "STATIC_URL",
        "LOGGING",
    }
    assert manifest["DEBUG"] == config.server.debug
    assert manifest["LANGUAGE_CODE"] == "en-us"
    assert manifest["TIME_ZONE"] == "UTC"
    assert manifest["USE_I18N"] is True
    assert manifest["USE_TZ"] is True
    assert manifest["STATIC_URL"] == "static/"
    assert list(manifest["TEMPLATES"]) == [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [],
            "APP_DIRS": True,
            "OPTIONS": {
                "context_processors": [
                    "django.template.context_processors.request",
                    "django.contrib.auth.context_processors.auth",
                    "django.contrib.messages.context_processors.messages",
                ],
            },
        }
    ]
    assert list(manifest["AUTH_PASSWORD_VALIDATORS"]) == [
        {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
        {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    ]
    assert manifest["LOGGING"]["version"] == 1
    assert manifest["LOGGING"]["disable_existing_loggers"] is False
    assert set(manifest["LOGGING"]["handlers"]) == {"console", "json_file"}
    assert manifest["LOGGING"]["loggers"]["django_structlog"]["level"] == "INFO"


def test_celery_manifest_matches_pre_refactor_values() -> None:
    """R2 acceptance: full key-by-key equivalence with the pre-refactor setup_celery output."""

    config = AppConfig.load()
    cfg = config.celery
    prefix = cfg.queue_prefix
    manifest = CelerySettingsBuilder.build(config, AssemblyContext(), installed_apps=[])

    assert set(manifest) == {
        "CELERY_BROKER_URL",
        "CELERY_BROKER_TRANSPORT_OPTIONS",
        "CELERY_TASK_IGNORE_RESULT",
        "CELERY_STORE_ERROR_EVEN_IF_IGNORED",
        "CELERY_TASK_SERIALIZER",
        "CELERY_ACCEPT_CONTENT",
        "CELERY_TIMEZONE",
        "CELERY_ENABLE_UTC",
        "CELERY_TASK_ACKS_LATE",
        "CELERY_TASK_REJECT_ON_WORKER_LOST",
        "CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT",
        "CELERY_WORKER_PREFETCH_MULTIPLIER",
        "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP",
        "CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS",
        "CELERY_TASK_SOFT_TIME_LIMIT",
        "CELERY_TASK_TIME_LIMIT",
        "CELERY_TASK_QUEUES",
        "CELERY_TASK_DEFAULT_QUEUE",
        "CELERY_TASK_DEFAULT_EXCHANGE",
        "CELERY_TASK_DEFAULT_EXCHANGE_TYPE",
        "CELERY_TASK_DEFAULT_ROUTING_KEY",
        "CELERY_TASK_CREATE_MISSING_QUEUES",
        "CELERY_IMPORTS",
    }
    assert manifest["CELERY_BROKER_TRANSPORT_OPTIONS"] == {"confirm_publish": True}
    assert manifest["CELERY_TASK_SERIALIZER"] == "json"
    assert manifest["CELERY_ACCEPT_CONTENT"] == ["json"]
    assert manifest["CELERY_WORKER_PREFETCH_MULTIPLIER"] == 1
    assert manifest["CELERY_TASK_SOFT_TIME_LIMIT"] == 240
    assert manifest["CELERY_TASK_TIME_LIMIT"] == 300
    assert manifest["CELERY_TASK_DEFAULT_QUEUE"] == f"{prefix}.default"
    assert manifest["CELERY_TASK_DEFAULT_EXCHANGE"] == f"{prefix}.exchange"
    assert manifest["CELERY_TASK_DEFAULT_EXCHANGE_TYPE"] == "direct"
    assert manifest["CELERY_TASK_DEFAULT_ROUTING_KEY"] == f"{prefix}.default"

    by_name = {queue.name: queue for queue in manifest["CELERY_TASK_QUEUES"]}
    assert set(by_name) == {
        f"{prefix}.urgent",
        f"{prefix}.high",
        f"{prefix}.default",
        f"{prefix}.low",
        f"{prefix}.internal",
        f"{prefix}.dlq",
    }
    for tier in ("urgent", "high", "default", "low"):
        args = by_name[f"{prefix}.{tier}"].queue_arguments
        assert args["x-queue-type"] == "quorum"
        assert args["x-dead-letter-exchange"] == f"{prefix}.dlx"
        assert args["x-dead-letter-routing-key"] == "dead"
    assert by_name[f"{prefix}.internal"].queue_arguments == {"x-queue-type": "quorum"}
    assert by_name[f"{prefix}.dlq"].queue_arguments == {"x-queue-type": "quorum"}
