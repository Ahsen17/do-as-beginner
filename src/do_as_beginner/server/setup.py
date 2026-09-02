from typing import Any, ClassVar

import structlog
from django.conf import LazySettings, settings
from kombu import Exchange, Queue
from pydantic import Field
from typer import Typer

from do_as_beginner.base import AppConfig, BaseStruct
from do_as_beginner.base.config.constants import APP_NAME, BASE_DIR

from .plugins import OtelPlugin, RedisPlugin

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

        settings.CELERY_BROKER_URL = self.config.celery.broker_dsn
        settings.CELERY_BROKER_TRANSPORT_OPTIONS = {"confirm_publish": True}
        settings.CELERY_TASK_IGNORE_RESULT = True
        settings.CELERY_STORE_ERROR_EVEN_IF_IGNORED = False
        settings.CELERY_TASK_SERIALIZER = "json"
        settings.CELERY_ACCEPT_CONTENT = ["json"]
        settings.CELERY_TIMEZONE = "Asia/Shanghai"
        settings.CELERY_ENABLE_UTC = True
        settings.CELERY_TASK_ACKS_LATE = True
        settings.CELERY_TASK_REJECT_ON_WORKER_LOST = True
        settings.CELERY_WORKER_PREFETCH_MULTIPLIER = 1
        settings.CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
        settings.CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True
        settings.CELERY_TASK_SOFT_TIME_LIMIT = 240
        settings.CELERY_TASK_TIME_LIMIT = 300
        settings.CELERY_TASK_TRACK_STARTED = True

        task_exchange = Exchange(name="dab.tasks.exchange", type="direct", durable=True)
        dead_letter_exchange = Exchange("dab.tasks.dlx", type="direct", durable=True)

        settings.CELERY_TASK_QUEUES = (
            Queue(
                name="dab.tasks",
                exchange=task_exchange,
                routing_key="tasks",
                durable=True,
                queue_arguments={
                    "x-queue-type": "quorum",
                    "x-delivery-limit": 5,
                    "x-dead-letter-exchange": dead_letter_exchange.name,
                    "x-dead-letter-routing-key": "dab",
                },
            ),
            Queue(
                name="dab.tasks.dlq",
                exchange=dead_letter_exchange,
                routing_key="dead",
                durable=True,
                queue_arguments={"x-queue-type": "quorum"},
            ),
        )
        settings.CELERY_TASK_DEFAULT_QUEUE = "dab.tasks"
        settings.CELERY_TASK_DEFAULT_EXCHANGE = "dab.tasks.exchange"
        settings.CELERY_TASK_DEFAULT_EXCHANGE_TYPE = "direct"
        settings.CELERY_TASK_DEFAULT_ROUTING_KEY = "tasks"
        settings.CELERY_TASK_DEFAULT_PRIORITY = 1
        settings.CELERY_TASK_CREATE_MISSING_QUEUES = False

    def setup_plugins(self) -> None:

        OtelPlugin(self.config).setup()
        RedisPlugin(self.config).setup()
