import os
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from multiprocessing import get_all_start_methods
from pathlib import Path
from typing import Any, ClassVar, Self

import jieba  # type: ignore
import mmh3
import numpy as np
from fastembed.parallel_processor import ParallelWorkerPool, Worker

from .schemas import SparseEmbedding
from .utils import iter_batch

__all__ = ("Bm25",)


class Bm25:
    """Bm25 sparse embedder for zhCN text using jieba tokenization"""

    _punctuation: ClassVar[re.Pattern[str]] = re.compile(
        pattern=r"[^\u4e00-\u9fffa-zA-Z0-9\-#]|\s+",
    )

    def __init__(
        self,
        *,
        k: float = 1.2,
        b: float = 0.75,
        avg_len: float = 256.0,
        token_max_length: int = 40,
        stopwords_files: Iterable[Path] | None = None,
    ) -> None:

        self._k = k
        self._b = b
        self._avg_len = avg_len
        self._token_max_length = token_max_length
        self._stopwords_files = stopwords_files
        self._tokenizer = self.tokenizer

        if self._avg_len <= 0:
            raise ValueError("avg_len must be greater than 0")
        if self._token_max_length <= 0:
            raise ValueError("token_max_length must be greater than 0")
        if self._k < 0:
            raise ValueError("k must be greater than or equal to 0")
        if self._b < 0 or self._b > 1:
            raise ValueError("b must be between 0 and 1")

        self._stopwords = self._load_stopwords(stopwords_files)

    @classmethod
    def tokenizer(cls, document: str) -> list[str]:

        if not document.strip():
            return []

        return list(
            jieba.cut_for_search(
                unicodedata.normalize("NFKC", document),
            )
        )

    @classmethod
    def compute_token_id(cls, token: str) -> int:
        return abs(mmh3.hash(token))

    @classmethod
    def _load_stopwords(
        cls,
        stopwords_files: Iterable[Path] | None = None,
    ) -> set[str]:

        stopwords: set[str] = set()
        if stopwords_files is None:
            return stopwords

        for file in stopwords_files:
            if not file.exists():
                continue

            for line in file.read_text().splitlines():
                if _line := line.strip():
                    stopwords.add(_line)

        return stopwords

    def _embed_documents(
        self,
        documents: str | Iterable[str],
        batch_size: int = 256,
        parallel: int | None = None,
    ) -> Iterable[SparseEmbedding]:

        is_small = False
        if isinstance(documents, str):
            documents = [documents]
            is_small = True

        if isinstance(documents, list) and len(documents) <= batch_size:
            is_small = True

        if parallel is None or is_small:
            for batch in iter_batch(documents, batch_size):
                yield from self.raw_embed(batch)

        else:
            if parallel == 0:
                parallel = os.cpu_count()

            start_method = "forkserver" if "forkserver" in get_all_start_methods() else "spawn"

            pool = ParallelWorkerPool(
                num_workers=parallel or 1,
                worker=self._get_worker_class(),
                start_method=start_method,
            )
            for batch in pool.ordered_map(
                iter_batch(
                    documents,
                    batch_size,
                ),
                k=self._k,
                b=self._b,
                avg_len=self._avg_len,
                token_max_length=self._token_max_length,
                stopwords_files=self._stopwords_files,
                tokenizer=self._tokenizer,
            ):
                yield from batch

    def _stem(self, tokens: list[str]) -> list[str]:

        stemmed_tokens: list[str] = []
        for token in tokens:
            if not self._punctuation.sub(" ", token).strip():
                continue

            if token.lower() in self._stopwords:
                continue

            if len(token) > self._token_max_length:
                continue

            stemmed_tokens.append(token.lower())

        return stemmed_tokens

    def _term_frequency(self, tokens: list[str]) -> dict[int, float]:
        """Calculate the term frequency part of the BM25 formula.

        (
            f(q_i, d) * (k + 1)
        ) / (
            f(q_i, d) + k * (1 - b + b * (|d| / avg_len))
        )
        """

        tf_map: dict[int, float] = {}
        counter: defaultdict[str, int] = defaultdict(int)
        for token in tokens:
            counter[token] += 1

        doc_len = len(tokens)
        for token in counter:
            token_id = self.compute_token_id(token)
            num_occurrences = counter[token]
            tf_map[token_id] = num_occurrences * (self._k + 1)
            tf_map[token_id] /= num_occurrences + self._k * (1 - self._b + self._b * doc_len / self._avg_len)

        return tf_map

    def raw_embed(self, documents: list[str]) -> list[SparseEmbedding]:

        embeddings: list[SparseEmbedding] = []

        for document in documents:
            tokens = self._tokenizer(document)
            stemmed_tokens = self._stem(tokens)
            token_id2value = self._term_frequency(stemmed_tokens)
            embeddings.append(
                SparseEmbedding(
                    values=list(token_id2value.values()),
                    indices=list(token_id2value.keys()),
                )
            )

        return embeddings

    def embed(
        self,
        documents: str | Iterable[str],
        batch_size: int = 256,
        parallel: int | None = None,
    ) -> Iterable[SparseEmbedding]:

        yield from self._embed_documents(
            documents,
            batch_size=batch_size,
            parallel=parallel,
        )

    def query_embed(self, query: str | Iterable[str]) -> Iterable[SparseEmbedding]:

        if isinstance(query, str):
            query = [query]

        for text in query:
            tokens = self._tokenizer(text)
            stemmed_tokens = self._stem(tokens)
            indices = np.array(
                [self.compute_token_id(token) for token in stemmed_tokens],
                dtype=np.int32,
            )
            values = np.ones_like(indices)

            yield SparseEmbedding(
                indices=sorted(indices.tolist()),
                values=values.tolist(),
            )

    @classmethod
    def _get_worker_class(cls) -> type[Worker]:

        return _Bm25Worker


class _Bm25Worker(Worker):
    """Worker class for Bm25 embedding"""

    def __init__(self, **kwargs: Any) -> None:

        self.model = Bm25(**kwargs)

    @classmethod
    def start(cls, **kwargs: Any) -> Self:

        return cls(**kwargs)

    def process(
        self,
        items: Iterable[tuple[int, Any]],
    ) -> Iterable[tuple[int, list[SparseEmbedding]]]:

        for idx, batch in items:
            yield idx, self.model.raw_embed(batch)
