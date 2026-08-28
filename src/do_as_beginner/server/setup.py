from typing import Any, ClassVar

from django.conf import settings
from pydantic import Field
from typer import Typer

from do_as_beginner.base import AppConfig, BaseStruct
from do_as_beginner.base.config.constants import APP_NAME, BASE_DIR

from .plugins import OtelPlugin

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

    def setup(self) -> None:
        """Setup plugin core."""

        self.setup_installed_apps()
        self.setup_middleware()
        self.setup_templates()
        self.setup_databases()
        self.setup_auth_password_validators()
        self.setup_plugins()

        settings.configure()

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

    def setup_plugins(self) -> None:

        OtelPlugin(self.config).setup()
