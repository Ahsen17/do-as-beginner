"""Django and Celery settings assembly.

``SettingsBuilder`` produces the Django settings manifest; ``CelerySettingsBuilder``
produces the ``CELERY_*`` manifest. Both merge the framework's built-in values
(derived from ``AppConfig``, equivalent to the pre-refactor ``setup.py`` output)
with plugin contributions from an :class:`~do_as_beginner.server.plugins.AssemblyContext`.
The combined manifests are applied in one ``settings.configure(**kwargs)`` call.
"""

import importlib.util
from typing import TYPE_CHECKING, Any

import structlog
from kombu import Exchange, Queue

from do_as_beginner.base import AppConfig
from do_as_beginner.base.config.constants import APP_NAME, BASE_DIR
from do_as_beginner.server.plugin import AssemblyContext, ContributionConflictError
from do_as_beginner.tasks.enums import QueueTier, queue_name

if TYPE_CHECKING:
    from do_as_beginner.base import CeleryConfig

__all__ = (
    "CelerySettingsBuilder",
    "SettingsBuilder",
)

_LOG_DIR = BASE_DIR / "logs"


def _discover_task_modules(installed_apps: list[str]) -> tuple[str, ...]:
    """Discover each installed app's ``<app>.tasks`` module, if it exists.

    ``autodiscover_tasks()`` does not scan INSTALLED_APPS reliably, so the
    discovered set (union plugin contributions) is the source of truth for
    ``CELERY_IMPORTS``.
    """

    return tuple(f"{app}.tasks" for app in installed_apps if importlib.util.find_spec(f"{app}.tasks") is not None)


class SettingsBuilder:
    """Builds the Django settings manifest from config plus plugin contributions."""

    @classmethod
    def build(cls, config: AppConfig, assembly: AssemblyContext) -> dict[str, Any]:
        """Return the manifest applied via ``settings.configure(**manifest)``"""

        installed_apps = cls.installed_apps(assembly)
        middlewares = [*cls.MIDDLEWARES, *assembly.middlewares]

        manifest: dict[str, Any] = {
            "SECRET_KEY": "django-insecure-1vh@c=j9x6n+@#8lw4&n3g)3y(jd!_+1ra-e4+xn=-4941h(())",
            "DEBUG": config.server.debug,
            "ALLOWED_HOSTS": ["*"],
            "INSTALLED_APPS": installed_apps,
            "MIDDLEWARE": middlewares,
            "ROOT_URLCONF": f"{APP_NAME}.server.core.routes",
            "TEMPLATES": cls.TEMPLATES,
            "DATABASES": cls.databases(config),
            "AUTH_PASSWORD_VALIDATORS": cls.AUTH_PASSWORD_VALIDATORS,
            "LANGUAGE_CODE": "en-us",
            "TIME_ZONE": "UTC",
            "USE_I18N": True,
            "USE_TZ": True,
            "STATIC_URL": "static/",
            "LOGGING": cls.logging(),
        }

        for key, value in assembly.extra_settings.items():
            if key in manifest:
                msg = f"Setting key {key!r} is framework-reserved and cannot be contributed"
                raise ContributionConflictError(msg)
            manifest[key] = value

        return manifest

    @staticmethod
    def installed_apps(assembly: AssemblyContext) -> list[str]:
        """Framework base apps plus plugin contributions (dedupe, keep order)."""

        apps: list[str] = []
        for app in [*SettingsBuilder.BASE_APPS, *assembly.installed_apps]:
            if app not in apps:
                apps.append(app)
        return apps

    @staticmethod
    def databases(config: AppConfig) -> dict[str, Any]:
        """The default async-PostgreSQL database (optional psycopg pool) plus the SQLite testing alias."""

        return {
            "default": {
                "ENGINE": "django_async_backend.db.backends.postgresql",
                "NAME": config.postgres.database,
                "USER": config.postgres.username,
                "PASSWORD": config.postgres.password,
                "HOST": config.postgres.host,
                "PORT": config.postgres.port,
                "OPTIONS": {
                    "pool": {
                        "min_size": config.postgres.pool_min_size,
                        "max_size": config.postgres.pool_max_size,
                    }
                    if config.postgres.pool_enabled
                    else {},
                },
            },
            "testing": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            },
        }

    @staticmethod
    def logging() -> dict[str, Any]:
        """Structlog-backed logging config: console (dev renderer) plus JSON file handler."""

        _LOG_DIR.mkdir(parents=True, exist_ok=True)

        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json_formatter": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.processors.JSONRenderer(),
                },
                "console_formatter": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "console_formatter",
                },
                "json_file": {
                    "class": "logging.handlers.WatchedFileHandler",
                    "filename": str(_LOG_DIR.joinpath("json.log").resolve()),
                    "formatter": "json_formatter",
                },
            },
            "loggers": {
                "django_structlog": {
                    "handlers": ["console", "json_file"],
                    "level": "INFO",
                },
            },
        }

    BASE_APPS: tuple[str, ...] = (
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        "django_async_backend",
        "django_structlog",
        "do_as_beginner.blobs",
        "do_as_beginner.tasks",
    )

    MIDDLEWARES: tuple[str, ...] = (
        "django.middleware.security.SecurityMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
        "django_structlog.middlewares.RequestMiddleware",
    )

    TEMPLATES: tuple[dict[str, Any], ...] = (
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
        },
    )

    AUTH_PASSWORD_VALIDATORS: tuple[dict[str, str], ...] = (
        {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
        {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    )


class CelerySettingsBuilder:
    """Builds the ``CELERY_*`` settings manifest (equivalent to the pre-refactor ``setup_celery``).

    Applied for all three entrypoints: the web process publishes tasks via
    ``send_task`` and reads broker/queue settings through
    ``config_from_object(..., namespace="CELERY")``.
    """

    @classmethod
    def build(cls, config: AppConfig, assembly: AssemblyContext, *, installed_apps: list[str]) -> dict[str, Any]:
        """Return the ``CELERY_*`` manifest (does not include ``CELERY_BEAT_SCHEDULE``).

        Beat entries are assembled in ``Scheduler.bootstrap`` after task import --
        code-declared ``@periodic_task`` entries and internal ticks are only
        visible then, and plugin contributions merge there too.

        Raises:
            ValueError: ``config.celery`` fails redelivery validation.
        """

        cfg = config.celery
        cfg.validate_redelivery()

        return {
            "CELERY_BROKER_URL": cfg.broker_dsn,
            "CELERY_BROKER_TRANSPORT_OPTIONS": {"confirm_publish": True},
            # No Celery result backend: with IGNORE_RESULT Celery itself persists nothing. Task
            # results/states are written by this framework to the dab_tasks app tables
            # (TaskTrace / DelayedRedelivery) via the lifecycle signals and dispatch hooks.
            "CELERY_TASK_IGNORE_RESULT": True,
            "CELERY_STORE_ERROR_EVEN_IF_IGNORED": False,
            "CELERY_TASK_SERIALIZER": "json",
            "CELERY_ACCEPT_CONTENT": ["json"],
            "CELERY_TIMEZONE": cfg.timezone,
            "CELERY_ENABLE_UTC": True,
            "CELERY_TASK_ACKS_LATE": True,
            "CELERY_TASK_REJECT_ON_WORKER_LOST": True,
            # acks_on_failure_or_timeout=False + acks_late: an unhandled failure is not acked, the
            # broker redelivers it, and after the quorum x-delivery-limit (<delivery_limit>) it is
            # dead-lettered to <prefix>.dlq instead of being silently dropped. Task code should catch
            # domain errors itself and let only unexpected errors surface.
            # NOTE: autoretry() re-publishes a fresh message that resets the broker delivery budget,
            # so the effective execution bound is (1 + autoretry) per broker delivery, not flat.
            # The exact interplay is to be verified by integration tests.
            "CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT": False,
            "CELERY_WORKER_PREFETCH_MULTIPLIER": 1,
            "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP": True,
            "CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS": True,
            "CELERY_TASK_SOFT_TIME_LIMIT": 240,
            "CELERY_TASK_TIME_LIMIT": 300,
            "CELERY_TASK_QUEUES": cls.tier_queues(cfg),
            "CELERY_TASK_DEFAULT_QUEUE": queue_name(cfg.queue_prefix, QueueTier.DEFAULT),
            "CELERY_TASK_DEFAULT_EXCHANGE": f"{cfg.queue_prefix}.exchange",
            "CELERY_TASK_DEFAULT_EXCHANGE_TYPE": "direct",
            "CELERY_TASK_DEFAULT_ROUTING_KEY": queue_name(cfg.queue_prefix, QueueTier.DEFAULT),
            "CELERY_TASK_CREATE_MISSING_QUEUES": False,
            "CELERY_IMPORTS": cls.task_imports(assembly, installed_apps),
        }

    @staticmethod
    def tier_queues(cfg: "CeleryConfig") -> tuple[Queue, ...]:
        """One quorum queue per tier plus the internal system queue and the DLQ.

        Each tier has its own dedicated workers so a high-priority flood cannot
        starve lower tiers (fairness floor = worker quota, not scheduling). The
        internal queue hosts periodic system tasks (DLQ drain, due-redelivery
        dispatch) in a dedicated worker, kept separate from user tiers.
        """

        prefix = cfg.queue_prefix
        task_exchange = Exchange(f"{prefix}.exchange", type="direct", durable=True)
        dead_letter_exchange = Exchange(f"{prefix}.dlx", type="direct", durable=True)

        tier_args = {
            "x-queue-type": "quorum",
            "x-delivery-limit": cfg.delivery_limit,
            "x-dead-letter-exchange": dead_letter_exchange.name,
            "x-dead-letter-routing-key": "dead",
        }
        tier_queues = tuple(
            Queue(
                name=queue_name(prefix, tier),
                exchange=task_exchange,
                routing_key=queue_name(prefix, tier),
                durable=True,
                queue_arguments=tier_args,
            )
            for tier in QueueTier
        )
        internal_queue = Queue(
            name=f"{prefix}.internal",
            exchange=task_exchange,
            routing_key=f"{prefix}.internal",
            durable=True,
            queue_arguments={"x-queue-type": "quorum"},
        )
        dead_letter_queue = Queue(
            name=f"{prefix}.dlq",
            exchange=dead_letter_exchange,
            routing_key="dead",
            durable=True,
            queue_arguments={"x-queue-type": "quorum"},
        )
        return (*tier_queues, internal_queue, dead_letter_queue)

    @staticmethod
    def task_imports(assembly: AssemblyContext, installed_apps: list[str]) -> tuple[str, ...]:
        """Auto-discovered ``<app>.tasks`` modules unioned with plugin contributions (dedupe, keep order)."""

        imports: list[str] = []
        for module in (*_discover_task_modules(installed_apps), *assembly.celery_task_modules):
            if module not in imports:
                imports.append(module)
        return tuple(imports)
