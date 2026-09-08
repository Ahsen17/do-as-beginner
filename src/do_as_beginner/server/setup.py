import importlib.util
from typing import Any, ClassVar

import structlog
from django.conf import LazySettings, settings
from kombu import Exchange, Queue
from pydantic import Field
from typer import Typer

from do_as_beginner.base import AppConfig, BaseStruct
from do_as_beginner.base.config.constants import APP_NAME, BASE_DIR
from do_as_beginner.tasks.enums import QueueTier, queue_name

from .di import get_default_container
from .plugins import OtelPlugin, QdrantPlugin, RedisPlugin

__all__ = ("PluginCore",)


class PluginCore(BaseStruct):
    """Plugin core configuration."""

    config: ClassVar[AppConfig] = AppConfig.load()
    typers: ClassVar[list[Typer]] = []

    installed_apps: list[str] = Field(default_factory=list)
    middlewares: list[str] = Field(default_factory=list)
    templates: list[dict[str, Any]] = Field(default_factory=list)
    databases: dict[str, Any] = Field(default_factory=dict)
    auth_password_validators: list[dict[str, str]] = Field(default_factory=list)
    logging: dict[str, Any] = Field(default_factory=dict)

    def setup(self) -> None:
        """Setup plugin core."""

        settings.configure()

        self.setup_installed_apps()
        self.setup_middleware()
        self.setup_templates()
        self.setup_databases()
        self.setup_auth_password_validators()
        self.setup_loggings()

        settings.SECRET_KEY = "django-insecure-1vh@c=j9x6n+@#8lw4&n3g)3y(jd!_+1ra-e4+xn=-4941h(()"  # noqa: S105
        settings.DEBUG = self.config.server.debug
        settings.ALLOWED_HOSTS = ["*"]
        settings.INSTALLED_APPS = self.installed_apps
        settings.MIDDLEWARE = self.middlewares
        settings.ROOT_URLCONF = f"{APP_NAME}.server.routes"
        settings.TEMPLATES = self.templates
        settings.DATABASES = self.databases
        settings.AUTH_PASSWORD_VALIDATORS = self.auth_password_validators
        settings.LANGUAGE_CODE = "en-us"
        settings.TIME_ZONE = "UTC"
        settings.USE_I18N = True
        settings.USE_TZ = True
        settings.STATIC_URL = "static/"
        settings.LOGGING = self.logging

        self.setup_celery(settings)
        self.setup_plugins()

    def setup_installed_apps(self) -> None:
        self.installed_apps.extend(
            [
                "django.contrib.admin",
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "django.contrib.sessions",
                "django.contrib.messages",
                "django.contrib.staticfiles",
                "django_async_backend",
                "django_structlog",
                "do_as_beginner.tasks",
            ]
        )

    def setup_middleware(self) -> None:
        self.middlewares.extend(
            [
                "django.middleware.security.SecurityMiddleware",
                "django.contrib.sessions.middleware.SessionMiddleware",
                "django.middleware.common.CommonMiddleware",
                "django.middleware.csrf.CsrfViewMiddleware",
                "django.contrib.auth.middleware.AuthenticationMiddleware",
                "django.contrib.messages.middleware.MessageMiddleware",
                "django.middleware.clickjacking.XFrameOptionsMiddleware",
                "django_structlog.middlewares.RequestMiddleware",
            ]
        )

    def setup_templates(self) -> None:
        self.templates.extend(
            [
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
            ]
        )

    def setup_databases(self) -> None:
        self.databases.update(
            {
                "default": {
                    "ENGINE": "django_async_backend.db.backends.postgresql",
                    "NAME": self.config.postgres.database,
                    "USER": self.config.postgres.username,
                    "PASSWORD": self.config.postgres.password,
                    "HOST": self.config.postgres.host,
                    "PORT": self.config.postgres.port,
                    "OPTIONS": {
                        "pool": {
                            "min_size": self.config.postgres.pool_min_size,
                            "max_size": self.config.postgres.pool_max_size,
                        }
                        if self.config.postgres.pool_enabled
                        else {},
                    },
                },
                "testing": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": BASE_DIR / "db.sqlite3",
                },
            }
        )

    def setup_auth_password_validators(self) -> None:
        self.auth_password_validators.extend(
            [
                {
                    "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
                },
                {
                    "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
                },
                {
                    "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
                },
                {
                    "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
                },
            ]
        )

    def setup_loggings(self) -> None:
        log_dir = BASE_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        self.logging = {
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
                    "filename": str(log_dir.joinpath("json.log").resolve()),
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

    def setup_celery(self, settings: LazySettings) -> None:
        cfg = self.config.celery
        cfg.validate_redelivery()

        settings.CELERY_BROKER_URL = cfg.broker_dsn
        settings.CELERY_BROKER_TRANSPORT_OPTIONS = {"confirm_publish": True}
        # No Celery result backend: with IGNORE_RESULT Celery itself persists nothing. Task
        # results/states are written by this framework to the dab_tasks app tables
        # (TaskTrace / DelayedRedelivery) via the lifecycle signals and dispatch hooks.
        settings.CELERY_TASK_IGNORE_RESULT = True
        settings.CELERY_STORE_ERROR_EVEN_IF_IGNORED = False
        settings.CELERY_TASK_SERIALIZER = "json"
        settings.CELERY_ACCEPT_CONTENT = ["json"]
        settings.CELERY_TIMEZONE = cfg.timezone
        settings.CELERY_ENABLE_UTC = True
        settings.CELERY_TASK_ACKS_LATE = True
        settings.CELERY_TASK_REJECT_ON_WORKER_LOST = True
        # acks_on_failure_or_timeout=False + acks_late: an unhandled failure is not acked, the
        # broker redelivers it, and after the quorum x-delivery-limit (<delivery_limit>) it is
        # dead-lettered to <prefix>.dlq instead of being silently dropped. Task code should catch
        # domain errors itself and let only unexpected errors surface.
        # NOTE: autoretry() re-publishes a fresh message that resets the broker delivery budget,
        # so the effective execution bound is (1 + autoretry) per broker delivery, not flat.
        # The exact interplay is to be verified by integration tests.
        settings.CELERY_TASK_ACKS_ON_FAILURE_OR_TIMEOUT = False
        settings.CELERY_WORKER_PREFETCH_MULTIPLIER = 1
        settings.CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
        settings.CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True
        settings.CELERY_TASK_SOFT_TIME_LIMIT = 240
        settings.CELERY_TASK_TIME_LIMIT = 300

        prefix = cfg.queue_prefix
        task_exchange = Exchange(f"{prefix}.exchange", type="direct", durable=True)
        dead_letter_exchange = Exchange(f"{prefix}.dlx", type="direct", durable=True)

        tier_args = {
            "x-queue-type": "quorum",
            "x-delivery-limit": cfg.delivery_limit,
            "x-dead-letter-exchange": dead_letter_exchange.name,
            "x-dead-letter-routing-key": "dead",
        }
        # One quorum queue per tier; each tier has its own dedicated workers so a high-priority
        # flood cannot starve lower tiers (fairness floor = worker quota, not scheduling).
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
        # Internal system queue: periodic system tasks (DLQ drain, due-redelivery dispatch) run
        # in a dedicated worker bound to it. Kept separate from user tiers.
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

        settings.CELERY_TASK_QUEUES = (*tier_queues, internal_queue, dead_letter_queue)
        settings.CELERY_TASK_DEFAULT_QUEUE = queue_name(prefix, QueueTier.DEFAULT)
        settings.CELERY_TASK_DEFAULT_EXCHANGE = task_exchange.name
        settings.CELERY_TASK_DEFAULT_EXCHANGE_TYPE = "direct"
        settings.CELERY_TASK_DEFAULT_ROUTING_KEY = queue_name(prefix, QueueTier.DEFAULT)
        settings.CELERY_TASK_CREATE_MISSING_QUEUES = False
        # Discover each installed app's ``<app>.tasks`` module so celery imports and registers
        # consumer tasks on startup. The default autodiscover_tasks() does not scan
        # INSTALLED_APPS reliably, so CELERY_IMPORTS is the source of truth.
        from importlib import util  # noqa: PLC0415

        task_modules = tuple(
            f"{app}.tasks" for app in self.installed_apps if util.find_spec(f"{app}.tasks") is not None
        )
        settings.CELERY_IMPORTS = task_modules
        # CELERY_BEAT_SCHEDULE is assembled in the celery entrypoint after task import
        # (so code-declared @periodic_task entries are visible) -- see asgi.celery_entrypoint.

        task_modules = tuple(
            f"{app}.tasks" for app in self.installed_apps if importlib.util.find_spec(f"{app}.tasks") is not None
        )
        settings.CELERY_IMPORTS = task_modules
        # CELERY_BEAT_SCHEDULE is assembled in the celery entrypoint after task import
        # (so code-declared @periodic_task entries are visible) -- see asgi.celery_entrypoint.

    def setup_plugins(self) -> None:
        OtelPlugin(self.config).setup()

        # plugins di injection
        container = get_default_container()

        for plugin in (
            RedisPlugin(self.config, container),
            QdrantPlugin(self.config, container),
        ):
            plugin.setup(**container.inject(plugin.setup))
