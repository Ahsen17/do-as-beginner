from collections.abc import AsyncGenerator
from functools import cached_property

from openai import AsyncOpenAI

from .protocol import EmbedderProtocol
from .schemas import Embedding, OpenAIEmbedderOptions

__all__ = ("OpenAIEmbedder",)


class OpenAIEmbedder(EmbedderProtocol):
    """Embedder based on OpenAI protocol"""

    def __init__(self, options: OpenAIEmbedderOptions) -> None:

        self._options = options

    @cached_property
    def client(self) -> AsyncOpenAI:

        return AsyncOpenAI(
            base_url=self._options.base_url,
            api_key=self._options.api_key,
        )

    async def embed(self, *document: str, dimensions: int = 2056) -> AsyncGenerator[Embedding]:

        for embedding in (
            await self.client.embeddings.create(
                input=(*document,),
                model=self._options.model_id,
                dimensions=dimensions,
            )
        ).data:
            yield Embedding(
                embedding=embedding.embedding,
                index=embedding.index,
            )
