from do_as_beginner.base.schemas import BaseStruct

__all__ = ("MasterConfig",)


class MasterConfig(BaseStruct):
    """Workers master election config."""

    lock_id: int = 7_301_826_419_003
    poll_interval: float = 5.0
    healthcheck_interval: float = 5.0
    shutdown_timeout: float = 10.0
