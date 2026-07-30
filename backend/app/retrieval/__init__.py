"""Course-content retrieval implementations."""

"""Local, same-deck course retrieval."""

from .embeddings import (
    DeterministicFakeEmbeddingProvider,
    EmbeddingProvider,
    LocalSentenceTransformerEmbeddingProvider,
)
from .models import EvidenceChunk, RetrievalDiagnostics, RetrievalResult

__all__ = [
    "DeterministicFakeEmbeddingProvider",
    "EmbeddingProvider",
    "EvidenceChunk",
    "LocalSentenceTransformerEmbeddingProvider",
    "RetrievalDiagnostics",
    "RetrievalResult",
]
