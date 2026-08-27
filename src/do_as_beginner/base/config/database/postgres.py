from do_as_beginner.base.config.constants import APP_NAME
from do_as_beginner.base.schemas import BaseStruct

__all__ = ("PostgresConfig",)


class PostgresConfig(BaseStruct):
    """Postgres database configuration."""

    host: str = "localhost"
    port: int = "5432"
    database: str = APP_NAME
    username: str = ""
    password: str = ""

    conn_max_age: int = 600

    pool_enabled: bool = True
    pool_min_size: int = 5
    pool_max_size: int = 20
    command_timeout: int = 60
