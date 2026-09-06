from do_as_beginner.base import BaseStruct

__all__ = (
    "Embedding",
    "OpenAIEmbedderOptions",
)


class Embedding(BaseStruct):
    """Embedding schema"""

    embedding: list[float]
    index: int


class OpenAIEmbedderOptions(BaseStruct):
    """Options for OpenAI Embedder"""

    base_url: str = ""
    api_key: str = ""
    model_id: str = ""
