"""Google Cloud Storage service.

Handles uploading documents and images to GCS, generating public URLs,
and cleaning up files on document deletion.

Bucket structure:
    gs://{bucket}/documents/{document_id}/{filename}   — original uploads
    gs://{bucket}/images/{document_id}/{index}.{ext}   — extracted images
"""

import logging
from uuid import UUID

from google.cloud import storage

from app.config import settings

logger = logging.getLogger(__name__)

_storage_client: storage.Client | None = None

# Mime type to file extension mapping
MIME_TO_EXT: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/bmp": "bmp",
    "image/tiff": "tiff",
    "image/webp": "webp",
    "image/svg+xml": "svg",
    "image/x-emf": "emf",
    "image/x-wmf": "wmf",
}


def _get_storage_client() -> storage.Client:
    """Get or create a GCS client (lazy singleton)."""
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client(project=settings.gcp_project_id)
    return _storage_client


def _get_bucket() -> storage.Bucket:
    """Get the configured GCS bucket."""
    if not settings.gcs_bucket_name:
        raise ValueError("GCS_BUCKET_NAME is not set. Please set it in your .env file.")
    client = _get_storage_client()
    return client.bucket(settings.gcs_bucket_name)


def get_public_url(gcs_uri: str) -> str:
    """Convert a gs:// URI to a public HTTPS URL.

    Assumes the bucket has uniform bucket-level access with public read.

    Args:
        gcs_uri: A GCS URI like gs://bucket/path/to/object.

    Returns:
        Public HTTPS URL.
    """
    # gs://bucket-name/path/to/object -> https://storage.googleapis.com/bucket-name/path/to/object
    if gcs_uri.startswith("gs://"):
        path = gcs_uri[5:]  # Remove "gs://"
        return f"https://storage.googleapis.com/{path}"
    return gcs_uri


def upload_document(
    document_id: UUID,
    filename: str,
    file_bytes: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload an original document file to GCS.

    Args:
        document_id: UUID of the document record.
        filename: Original filename (e.g. "lecture.pdf").
        file_bytes: Raw file content.
        content_type: MIME type of the file.

    Returns:
        GCS URI (gs://bucket/documents/{document_id}/{filename}).
    """
    bucket = _get_bucket()
    blob_path = f"documents/{document_id}/{filename}"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(file_bytes, content_type=content_type)
    gcs_uri = f"gs://{settings.gcs_bucket_name}/{blob_path}"
    logger.info("Uploaded document to %s", gcs_uri)
    return gcs_uri


def upload_image(
    document_id: UUID,
    image_index: int,
    image_bytes: bytes,
    mime_type: str = "image/png",
) -> str:
    """Upload an extracted image to GCS.

    Args:
        document_id: UUID of the parent document.
        image_index: Order index of the image within the document.
        image_bytes: Raw image bytes.
        mime_type: MIME type of the image.

    Returns:
        GCS URI (gs://bucket/images/{document_id}/{index}.{ext}).
    """
    ext = MIME_TO_EXT.get(mime_type, "png")
    bucket = _get_bucket()
    blob_path = f"images/{document_id}/{image_index}.{ext}"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(image_bytes, content_type=mime_type)
    gcs_uri = f"gs://{settings.gcs_bucket_name}/{blob_path}"
    logger.info("Uploaded image to %s", gcs_uri)
    return gcs_uri


def delete_document_files(document_id: UUID) -> int:
    """Delete all GCS files associated with a document.

    Removes both the original document and all extracted images.

    Args:
        document_id: UUID of the document to clean up.

    Returns:
        Number of blobs deleted.
    """
    bucket = _get_bucket()
    deleted = 0

    # Delete original document files
    for blob in bucket.list_blobs(prefix=f"documents/{document_id}/"):
        blob.delete()
        deleted += 1

    # Delete extracted images
    for blob in bucket.list_blobs(prefix=f"images/{document_id}/"):
        blob.delete()
        deleted += 1

    if deleted:
        logger.info("Deleted %d GCS objects for document %s", deleted, document_id)
    return deleted
