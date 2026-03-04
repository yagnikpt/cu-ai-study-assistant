"""Embedding service.

Generates text embeddings via Gemini (gemini-embedding-001, 768-dim) and
image embeddings via Vertex AI multimodal model (multimodalembedding@001, 1408-dim).

Text embeddings use the google-genai SDK through the shared Vertex AI client.
Image embeddings use the google-cloud-aiplatform SDK (vertexai.vision_models).

All SDK calls are synchronous under the hood, so they are run via
``asyncio.to_thread`` to avoid blocking the event loop.
"""

import asyncio
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import vertexai
from google.genai import types
from vertexai.vision_models import Image as VMImage
from vertexai.vision_models import MultiModalEmbeddingModel

from app.config import settings
from app.services.genai_client import get_genai_client

logger = logging.getLogger(__name__)


@dataclass
class ImageEmbeddingResult:
    """Result of embedding a single image: vector + AI-generated caption."""

    embedding: list[float] = field(default_factory=list)
    caption: str = ""


# ── Vertex AI initialization (lazy) ──────────────────────

_vertexai_initialized: bool = False
_mm_model: MultiModalEmbeddingModel | None = None


def _ensure_vertexai() -> None:
    """Initialize Vertex AI SDK once (required for vision_models)."""
    global _vertexai_initialized
    if not _vertexai_initialized:
        vertexai.init(
            project=settings.gcp_project_id,
            location=settings.gcp_location,
        )
        _vertexai_initialized = True


def _get_mm_model() -> MultiModalEmbeddingModel:
    """Get or create the multimodal embedding model (lazy singleton)."""
    global _mm_model
    if _mm_model is None:
        _ensure_vertexai()
        _mm_model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")
    return _mm_model


# ── Text Embeddings (gemini-embedding-001 via genai SDK) ──


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts using Gemini.

    Args:
        texts: List of text strings to embed. Max ~2048 tokens each.

    Returns:
        List of embedding vectors (each is a list of 768 floats).

    Raises:
        ValueError: If the GCP project is not configured.
        Exception: On API errors.
    """
    if not texts:
        return []

    client = get_genai_client()
    embeddings: list[list[float]] = []

    # Process in batches of 100 (Gemini API limit)
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]

        # client.models.embed_content is synchronous — run in thread pool
        result = await asyncio.to_thread(
            client.models.embed_content,
            model=settings.embedding_model,
            contents=batch,
            config=types.EmbedContentConfig(
                output_dimensionality=settings.embedding_dimensions,
            ),
        )

        if result.embeddings:
            for embedding in result.embeddings:
                embeddings.append(list(embedding.values or []))

    logger.info(f"Generated {len(embeddings)} text embeddings")
    return embeddings


async def embed_query(text: str) -> list[float]:
    """Generate an embedding for a single query text.

    Args:
        text: The query text to embed.

    Returns:
        Embedding vector (list of 768 floats).
    """
    results = await embed_texts([text])
    return results[0]


# ── Image Embeddings (multimodalembedding@001 via Vertex AI) ──


async def embed_images(image_bytes_list: list[bytes]) -> list[ImageEmbeddingResult]:
    """Generate multimodal embeddings and captions for a list of images.

    Uses Vertex AI's multimodalembedding model which produces 1408-dim
    vectors. A Gemini caption is generated for each image and used both
    as contextual text for better embeddings and stored for later display.

    Args:
        image_bytes_list: List of raw image byte arrays.

    Returns:
        List of ImageEmbeddingResult (embedding vector + caption).
        Returns an empty embedding for an image if embedding fails.
    """
    if not image_bytes_list:
        return []

    client = get_genai_client()
    model = _get_mm_model()
    results: list[ImageEmbeddingResult] = []

    for img_bytes in image_bytes_list:
        try:
            # Write to temp file — VMImage.load_from_file requires a path
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(img_bytes)
                tmp_path = tmp.name
            image = VMImage.load_from_file(tmp_path)

            # generate_content is synchronous — run in thread pool
            caption_response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(
                        data=img_bytes,
                        mime_type="image/jpeg",
                    ),
                    "Caption this image in less than 512 chars.",
                ],
            )
            caption = caption_response.text or ""

            # get_embeddings is synchronous — run in thread pool
            emb_response = await asyncio.to_thread(
                model.get_embeddings,
                image=image,
                contextual_text=caption,
                dimension=settings.image_embedding_dimensions,
            )
            results.append(
                ImageEmbeddingResult(
                    embedding=emb_response.image_embedding,
                    caption=caption,
                )
            )

            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

        except Exception:
            logger.warning(
                "Failed to embed image, using empty embedding", exc_info=True
            )
            results.append(ImageEmbeddingResult())
            # Clean up on error too
            try:
                Path(tmp_path).unlink(missing_ok=True)  # type: ignore[possibly-undefined]
            except Exception:
                pass

    logger.info(f"Generated {len(results)} image embeddings")
    return results


async def embed_image(image_bytes: bytes) -> ImageEmbeddingResult:
    """Generate a multimodal embedding and caption for a single image.

    Args:
        image_bytes: Raw image bytes.

    Returns:
        ImageEmbeddingResult with embedding vector and caption.
    """
    results = await embed_images([image_bytes])
    return results[0]


async def embed_query_multimodal(text: str) -> list[float]:
    """Generate a 1408-dim text embedding in the multimodal embedding space.

    Uses the same multimodalembedding@001 model that embeds images, so the
    resulting vector is directly comparable to image embeddings via cosine
    distance.

    Args:
        text: The query text to embed.

    Returns:
        Embedding vector (list of 1408 floats).
    """
    model = _get_mm_model()
    # get_embeddings is synchronous — run in thread pool
    response = await asyncio.to_thread(
        model.get_embeddings,
        contextual_text=text,
        dimension=settings.image_embedding_dimensions,
    )
    if not response.text_embedding:
        raise ValueError("Multimodal model returned no text embedding")
    return response.text_embedding
