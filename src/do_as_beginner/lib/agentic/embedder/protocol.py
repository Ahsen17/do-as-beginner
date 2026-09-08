from collections.abc import AsyncGenerator
from typing import Protocol

from .schemas import Embedding

__all__ = ("EmbedderProtocol",)


class EmbedderProtocol(Protocol):
    async def embed(
        self,
        *document: str,
        dimensions: int = 2056,
    ) -> AsyncGenerator[Embedding]: ...
