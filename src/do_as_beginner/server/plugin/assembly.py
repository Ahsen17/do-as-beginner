from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from typing import Any

from pydantic import ConfigDict, Field

from do_as_beginner.base import BaseStruct

from .constants import RESERVED_SETTING_KEYS
from .exceptions import ContributionConflictError

__all__ = ("AssemblyContext",)


class AssemblyContext(BaseStruct):
    """Aggregate assembly object collected before ``settings.configure()``"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    installed_apps: list[str] = Field(default_factory=list)
    middlewares: list[str] = Field(default_factory=list)
    extra_settings: dict[str, Any] = Field(default_factory=dict)
    celery_task_modules: list[str] = Field(default_factory=list)
    celery_beat_schedule: dict[str, dict[str, Any]] = Field(default_factory=dict)
    lifespans: list[Callable[[], AbstractContextManager[Any] | AbstractAsyncContextManager[Any]]] = Field(
        default_factory=list,
    )

    def add_installed_app(self, app: str) -> None:
        """Append an INSTALLED_APPS entry; duplicates are ignored (dedupe, keep order)."""

        if app not in self.installed_apps:
            self.installed_apps.append(app)

    def add_middleware(self, path: str) -> None:
        """Append a MIDDLEWARE entry (order is semantic, no dedupe)."""

        self.middlewares.append(path)

    def add_setting(self, key: str, value: Any) -> None:
        """Contribute an extra Django setting (later contributions overwrite earlier ones).

        Raises:
            ValueError: ``key`` is not all-uppercase.
            ContributionConflictError: ``key`` is framework-reserved.
        """

        if not key.isupper():
            msg = f"Setting key {key!r} must be all-uppercase"
            raise ValueError(msg)
        if key in RESERVED_SETTING_KEYS:
            msg = f"Setting key {key!r} is framework-reserved and cannot be contributed"
            raise ContributionConflictError(msg)
        self.extra_settings[key] = value

    def add_celery_task_module(self, module: str) -> None:
        """Contribute a Celery task module import path; duplicates are ignored."""

        if module not in self.celery_task_modules:
            self.celery_task_modules.append(module)

    def add_beat_entry(self, name: str, entry: dict[str, Any]) -> None:
        """Contribute a Celery beat schedule entry (later writes overwrite earlier ones)."""

        self.celery_beat_schedule[name] = entry

    def add_lifespan(
        self,
        factory: Callable[[], AbstractContextManager[Any] | AbstractAsyncContextManager[Any]],
    ) -> None:
        """Register a resource-lifetime context manager factory.

        The factory is called at ASGI lifespan startup (declaration order) and its
        context exits at lifespan shutdown in reverse order. Both sync and async
        context managers are accepted.
        """

        self.lifespans.append(factory)
