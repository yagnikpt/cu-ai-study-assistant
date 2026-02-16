"""Gemini embeddings service.

Generates text embeddings using Google's gemini-embedding-001 model.
Uses output_dimensionality to reduce vectors to 768 dimensions for
compatibility with pgvector HNSW index (max 2000 dims).
Supports batched embedding calls for efficiency.
"""

import logging

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Get or create a Gemini client (lazy singleton)."""
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please set it in your .env file."
            )
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts using Gemini.

    Args:
        texts: List of text strings to embed. Max ~2048 tokens each.

    Returns:
        List of embedding vectors (each is a list of 768 floats).

    Raises:
        ValueError: If the API key is not set.
        Exception: On API errors.
    """
    if not texts:
        return []

    client = _get_client()
    embeddings: list[list[float]] = []

    # Process in batches of 100 (Gemini API limit)
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]

        result = client.models.embed_content(
            model=settings.embedding_model,
            contents=batch,
            config=types.EmbedContentConfig(
                output_dimensionality=settings.embedding_dimensions,
            ),
        )

        if result.embeddings:
            for embedding in result.embeddings:
                embeddings.append(list(embedding.values or []))

    logger.info(f"Generated {len(embeddings)} embeddings")
    return embeddings


async def embed_query(text: str) -> list[float]:
    """Generate an embedding for a single query text.

    Uses the same model but can potentially use a different task type
    for retrieval queries in the future.

    Args:
        text: The query text to embed.

    Returns:
        Embedding vector (list of 768 floats).
    """
    results = await embed_texts([text])
    return results[0]
