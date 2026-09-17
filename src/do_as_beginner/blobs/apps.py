"""App config for the dab blob-storage Django app."""

from django.apps import AppConfig

__all__ = ("BlobsAppConfig",)


class BlobsAppConfig(AppConfig):
    """App config for the dab blob-storage Django app."""

    name = "do_as_beginner.blobs"
    label = "dab_blobs"
    verbose_name = "dab blob storage"
    default_auto_field = "django.db.models.BigAutoField"
