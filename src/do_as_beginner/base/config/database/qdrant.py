from do_as_beginner.base.schemas import BaseStruct

__all__ = ("QdrantConfig",)


class QdrantConfig(BaseStruct):
    """Configuration for Qdrant database"""

    location: str | None = None
    url: str | None = None
    port: int = 6333
    grpc_port: int = 6334
    prefer_grpc: bool = False
    https: bool = False
    api_key: str | None = None
    prefix: str | None = None
    timeout: int = 10000
    host: str | None = None
    path: str | None = None
    pool_size: int = 50
    headers: dict[str, str] | None = None
