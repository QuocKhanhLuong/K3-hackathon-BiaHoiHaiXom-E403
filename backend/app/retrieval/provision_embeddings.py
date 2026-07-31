"""Explicit build-time provisioning for the local semantic retrieval model."""

from backend.app.retrieval.embeddings import LocalSentenceTransformerEmbeddingProvider
from backend.app.retrieval.local_slides import DEFAULT_CACHE_DIR


def main() -> None:
    """Place model weights in the generated cache before the service starts."""
    provider = LocalSentenceTransformerEmbeddingProvider(
        cache_dir=DEFAULT_CACHE_DIR / "models"
    )
    provider.provision()
    print({"provider": provider.name, "cache_dir": str(provider.cache_dir)})


if __name__ == "__main__":
    main()
