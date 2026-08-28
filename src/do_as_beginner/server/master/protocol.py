from typing import Protocol

__all__ = ("ElectorProtocol",)


class ElectorProtocol(Protocol):
    """Master elector protocol"""

    async def acquire(self) -> bool: ...
    async def healthcheck(self) -> bool: ...
    async def release(self) -> None: ...
