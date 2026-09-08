from do_as_beginner.base import BaseStruct

__all__ = (
    "Embedding",
    "OpenAIEmbedderOptions",
    "SparseEmbedding",
)


class SparseEmbedding(BaseStruct):
    """Sparse embedding schema"""

    values: list[float]
    indices: list[int]


class Embedding(BaseStruct):
    """Embedding schema"""

    embedding: list[float]
    index: int


class OpenAIEmbedderOptions(BaseStruct):
    """Options for OpenAI Embedder"""

    base_url: str = ""
    api_key: str = ""
    model_id: str = ""
