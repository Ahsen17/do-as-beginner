from do_as_beginner.base.schemas import BaseStruct

__all__ = ("CeleryConfig",)


class CeleryConfig(BaseStruct):
    """Configuration for Celery"""

    broker_dsn: str = "amqp://guest:guest@localhost:5672//"
