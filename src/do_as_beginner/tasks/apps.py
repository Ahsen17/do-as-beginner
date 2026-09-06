from django.apps import AppConfig

__all__ = ("TasksConfig",)


class TasksConfig(AppConfig):
    """App config for the dab task-tracing Django app."""

    name = "do_as_beginner.tasks"
    label = "dab_tasks"
    verbose_name = "dab task tracing"
    default_auto_field = "django.db.models.BigAutoField"
