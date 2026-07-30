"""Offline embedding providers used by the lightweight local RAG index."""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Protocol


class EmbeddingProvider(Protocol):
    """Minimal provider boundary; it deliberately has no network API."""

    name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class LocalSentenceTransformerEmbeddingProvider:
    """Lazy local-only sentence-transformers provider.

    ``local_files_only`` prevents a request path from downloading model weights.
    Deployments that want semantic retrieval pre-provision this model in the
    sentence-transformers cache; otherwise retrieval deterministically falls
    back to BM25.
    """

    name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(
        self,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        cache_dir: Path | None = None,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.model_name,
                cache_folder=str(self.cache_dir) if self.cache_dir else None,
                local_files_only=True,
            )
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._get_model().encode(texts, normalize_embeddings=True)
        return [list(map(float, vector)) for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class DeterministicFakeEmbeddingProvider:
    """Small hashed bag-of-token provider for offline unit tests only."""

    name = "deterministic-fake"

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"[\wÀ-ỹ%+\-=/]+", text.casefold()):
            slot = (
                int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
                % self.dimensions
            )
            vector[slot] += 1.0
        magnitude = math.sqrt(sum(value * value for value in vector))
        return [value / magnitude for value in vector] if magnitude else vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
