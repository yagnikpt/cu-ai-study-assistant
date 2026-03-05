"""GCP credential resolver.

In **production** (``GCP_SERVICE_ACCOUNT_JSON`` is set), credentials are
loaded from the JSON string stored in that environment variable.

In **development** (``GCP_SERVICE_ACCOUNT_JSON`` is empty), credentials
fall back to Application Default Credentials — i.e. whatever
``gcloud auth application-default login`` has configured locally.
"""

import json
import logging

from google.auth import default as google_auth_default
from google.auth.credentials import Credentials
from google.oauth2 import service_account

from app.config import settings

logger = logging.getLogger(__name__)

_credentials: Credentials | None = None

# Scopes required by the GCP services we use (GCS, Vertex AI, GenAI).
_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def get_gcp_credentials() -> Credentials:
    """Return GCP credentials (lazy singleton).

    - Production: parsed from ``GCP_SERVICE_ACCOUNT_JSON``.
    - Development: Application Default Credentials (ADC).
    """
    global _credentials
    if _credentials is not None:
        return _credentials

    if settings.gcp_service_account_json:
        info = json.loads(settings.gcp_service_account_json)
        _credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=_SCOPES,
        )
        logger.info(
            "Using service-account credentials (email=%s)",
            _credentials.service_account_email,
        )
    else:
        _credentials, _ = google_auth_default(scopes=_SCOPES)
        logger.info("Using Application Default Credentials (ADC)")

    return _credentials
