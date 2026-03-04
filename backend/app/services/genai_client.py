"""Shared Google GenAI client.

Provides a centralized Gemini client configured for Vertex AI using
Application Default Credentials (ADC). All services should import
`get_genai_client` from here instead of creating their own clients.

Setup:
    - Run `gcloud auth application-default login` for local development.
    - On GCP infrastructure, ADC is available automatically.
    - Set GCP_PROJECT_ID and GCP_LOCATION in your .env file.
"""

import logging

from google import genai

from app.config import settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None
_async_client_initialized: bool = False


def get_genai_client() -> genai.Client:
    """Get or create a Gemini client via Vertex AI (lazy singleton).

    Uses Application Default Credentials with the project/location
    configured in settings.

    Returns:
        A configured genai.Client instance.

    Raises:
        ValueError: If GCP project ID is not set.
    """
    global _client
    if _client is None:
        if not settings.gcp_project_id:
            raise ValueError(
                "GCP_PROJECT_ID is not set. Please set it in your .env file."
            )
        _client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
        )
        logger.info(
            "Initialized Gemini client (Vertex AI) for project=%s, location=%s",
            settings.gcp_project_id,
            settings.gcp_location,
        )
    return _client
