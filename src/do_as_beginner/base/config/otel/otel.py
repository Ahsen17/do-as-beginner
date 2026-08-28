from do_as_beginner.base.schemas import BaseStruct

__all__ = ("OtelConfig",)


class OtelConfig(BaseStruct):
    """Configuration for open-telemetry."""

    enabled: bool = False
    endpoint: str = "localhost:4317"
