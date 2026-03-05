"""Shared Google GenAI client.

Provides a centralized Gemini client configured for Vertex AI.
All services should import `get_genai_client` from here instead of
creating their own clients.

Credentials:
    - **Production**: Set ``GCP_SERVICE_ACCOUNT_JSON`` to the raw JSON
      string of a service-account key. The client is initialised with
      explicit credentials.
    - **Development**: Leave ``GCP_SERVICE_ACCOUNT_JSON`` empty and run
      ``gcloud auth application-default login``.  ADC is used
      automatically.
"""

import logging

from google import genai

from app.config import settings
from app.services.gcp_credentials import get_gcp_credentials

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def get_genai_client() -> genai.Client:
    """Get or create a Gemini client via Vertex AI (lazy singleton).

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
        credentials = get_gcp_credentials()
        _client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_location,
            credentials=credentials,
        )
        logger.info(
            "Initialized Gemini client (Vertex AI) for project=%s, location=%s",
            settings.gcp_project_id,
            settings.gcp_location,
        )
    return _client
