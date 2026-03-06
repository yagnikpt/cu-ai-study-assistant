"""Document management router.

Handles file uploads, document CRUD, tagging, and chunk viewing.
Documents and extracted images are uploaded to GCS for persistence.
Supports PDF, DOCX, and PPTX file formats.
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.dependencies import DBSession
from app.models import (
    Document,
    DocumentChunk,
    DocumentImage,
    DocumentStatus,
    ImageIngestionProgress,
    IngestionProgress,
    Space,
    Tag,
    document_tags,
)
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentImageResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentTagsUpdate,
    DocumentUpdate,
    TagResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/spaces/{space_id}/documents", tags=["documents"])


async def _run_ingestion_pipeline(
    document_id: uuid.UUID, file_bytes: bytes, original_filename: str
) -> None:
    """Background task: upload to GCS, parse, chunk, embed, store images.

    This runs outside the request lifecycle with its own DB session.
    Supports PDF, DOCX, and PPTX formats via the unified document loader.

    Progress tracking:
      - `progress` follows the file/chunks pipeline (uploading -> parsing ->
        chunking -> embedding -> storing -> done).
      - `images_progress` follows image processing separately (pending ->
        uploading -> embedding -> storing -> done | skipped).
    """
    from app.database import async_session_factory
    from app.services.chunker import chunk_pages
    from app.services.document_loader import load_document
    from app.services.embeddings import embed_images, embed_texts
    from app.services.storage import upload_document, upload_image

    async with async_session_factory() as db:
        try:
            doc = await db.get(Document, document_id)
            if not doc:
                logger.error(f"Document {document_id} not found for ingestion")
                return

            # -- Progress: uploading ------------------------------------------------
            doc.progress = IngestionProgress.UPLOADING
            doc.images_progress = ImageIngestionProgress.PENDING
            await db.commit()

            # Step 1: Upload original file to GCS (sync — run in thread pool)
            logger.info(f"Uploading document to GCS: {doc.original_filename}")
            gcs_uri = await asyncio.to_thread(
                upload_document,
                document_id=document_id,
                filename=original_filename,
                file_bytes=file_bytes,
            )
            doc.file_path = gcs_uri

            # -- Progress: parsing --------------------------------------------------
            doc.progress = IngestionProgress.PARSING
            await db.commit()

            # Step 2: Parse document from bytes (sync — run in thread pool)
            logger.info(f"Parsing document: {doc.original_filename}")
            parsed = await asyncio.to_thread(
                load_document, original_filename, file_bytes
            )
            doc.page_count = parsed.page_count

            # -- Progress: chunking -------------------------------------------------
            doc.progress = IngestionProgress.CHUNKING
            await db.commit()

            # Step 3: Chunk the parsed pages (sync — run in thread pool)
            logger.info("Chunking document into semantic chunks")
            chunks = await asyncio.to_thread(
                chunk_pages,
                parsed.pages,
                settings.chunk_size,
                settings.chunk_overlap,
            )

            if not chunks:
                doc.status = DocumentStatus.FAILED
                doc.progress = None
                doc.images_progress = None
                doc.error_message = (
                    "No text content could be extracted from the document."
                )
                await db.commit()
                return

            # -- Progress: embedding ------------------------------------------------
            doc.progress = IngestionProgress.EMBEDDING
            await db.commit()

            # Step 4: Embed all text chunks
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            chunk_texts = [c.content for c in chunks]
            embeddings = await embed_texts(chunk_texts)

            # -- Progress: storing --------------------------------------------------
            doc.progress = IngestionProgress.STORING
            await db.commit()

            # Step 5: Store text chunks in DB
            for chunk, embedding in zip(chunks, embeddings):
                db_chunk = DocumentChunk(
                    document_id=document_id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    section_title=chunk.section_title,
                    embedding=embedding,
                    token_count=chunk.token_count,
                    metadata_=chunk.metadata,
                )
                db.add(db_chunk)

            # -- Progress: main pipeline done ---------------------------------------
            doc.progress = IngestionProgress.DONE
            await db.commit()

            # Step 6: Upload images to GCS + embed + store
            if parsed.images:
                logger.info(f"Processing {len(parsed.images)} images")

                # -- Images progress: uploading -------------------------------------
                doc.images_progress = ImageIngestionProgress.UPLOADING
                await db.commit()

                # Upload each image to GCS (sync — run in thread pool)
                image_gcs_uris: list[str] = []
                image_bytes_list: list[bytes] = []
                for idx, img in enumerate(parsed.images):
                    img_gcs_uri = await asyncio.to_thread(
                        upload_image,
                        document_id=document_id,
                        image_index=idx,
                        image_bytes=img.data,
                        mime_type=img.mime_type,
                    )
                    image_gcs_uris.append(img_gcs_uri)
                    image_bytes_list.append(img.data)

                # -- Images progress: embedding -------------------------------------
                doc.images_progress = ImageIngestionProgress.EMBEDDING
                await db.commit()

                # Generate multimodal embeddings + captions for images
                logger.info(
                    f"Generating image embeddings for {len(image_bytes_list)} images"
                )
                image_embed_results = await embed_images(image_bytes_list)

                # -- Images progress: storing ---------------------------------------
                doc.images_progress = ImageIngestionProgress.STORING
                await db.commit()

                # Store DocumentImage records
                for idx, img in enumerate(parsed.images):
                    emb_result = (
                        image_embed_results[idx]
                        if idx < len(image_embed_results)
                        else None
                    )
                    db_image = DocumentImage(
                        document_id=document_id,
                        gcs_uri=image_gcs_uris[idx],
                        page_number=img.page_number,
                        image_index=idx,
                        mime_type=img.mime_type,
                        caption=emb_result.caption if emb_result else None,
                        embedding=emb_result.embedding
                        if emb_result and emb_result.embedding
                        else None,
                    )
                    db.add(db_image)

                # -- Images progress: done ------------------------------------------
                doc.images_progress = ImageIngestionProgress.DONE
            else:
                doc.images_progress = ImageIngestionProgress.SKIPPED

            doc.status = DocumentStatus.READY
            await db.commit()
            logger.info(
                f"Ingestion complete: {doc.original_filename} "
                f"({len(chunks)} chunks, {len(parsed.images)} images)"
            )

        except Exception as e:
            logger.exception(f"Ingestion failed for document {document_id}: {e}")
            doc = await db.get(Document, document_id)
            if doc:
                doc.status = DocumentStatus.FAILED
                doc.progress = None
                doc.images_progress = None
                doc.error_message = str(e)[:1000]
                await db.commit()


@router.post("/", response_model=DocumentResponse, status_code=201)
async def upload_document(
    db: DBSession,
    background_tasks: BackgroundTasks,
    space_id: uuid.UUID,
    file: UploadFile,
):
    """Upload a document and start the ingestion pipeline.

    Supports PDF, DOCX, and PPTX formats. The document will be:
    1. Uploaded to GCS for persistent storage
    2. Parsed for text + image extraction
    3. Semantically chunked
    4. Text + image embedding generation
    5. Stored in vector database with GCS references

    Check the document's `status` field to track progress:
    - `processing`: Ingestion is in progress
    - `ready`: Document is fully indexed and searchable
    - `failed`: An error occurred (see `error_message`)
    """
    from app.services.document_loader import SUPPORTED_EXTENSIONS

    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    from pathlib import PurePosixPath

    file_ext = PurePosixPath(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: '{file_ext}'. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    if file.size and file.size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB.",
        )

    # Read file into memory
    file_bytes = await file.read()
    file_size = len(file_bytes)

    # Validate space exists
    space = await db.get(Space, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")

    # Create document record (file_path set during ingestion after GCS upload)
    doc = Document(
        filename=f"{uuid.uuid4()}{file_ext}",
        original_filename=file.filename,
        file_path="",  # will be updated with GCS URI during ingestion
        file_size_bytes=file_size,
        space_id=space_id,
        status=DocumentStatus.PROCESSING,
    )
    db.add(doc)
    await db.commit()

    # Kick off background ingestion with in-memory bytes
    background_tasks.add_task(
        _run_ingestion_pipeline, doc.id, file_bytes, file.filename
    )

    # Return response with chunk_count=0 since processing hasn't started
    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        status=doc.status.value,
        progress=doc.progress.value if doc.progress else None,
        images_progress=doc.images_progress.value if doc.images_progress else None,
        error_message=doc.error_message,
        chunk_count=0,
        tags=[],
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    db: DBSession,
    space_id: uuid.UUID,
    status: str | None = Query(None),
    tag_id: uuid.UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List documents in this space with optional filters."""
    query = (
        select(Document)
        .options(selectinload(Document.tags))
        .where(Document.space_id == space_id)
    )

    if status:
        query = query.where(Document.status == status)
    if tag_id:
        query = query.join(document_tags).where(document_tags.c.tag_id == tag_id)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Fetch page
    query = query.order_by(Document.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    documents = result.scalars().all()

    # Get chunk counts
    doc_ids = [d.id for d in documents]
    chunk_counts: dict[uuid.UUID, int] = {}
    image_counts: dict[uuid.UUID, int] = {}
    if doc_ids:
        chunk_count_query = (
            select(DocumentChunk.document_id, func.count(DocumentChunk.id))
            .where(DocumentChunk.document_id.in_(doc_ids))
            .group_by(DocumentChunk.document_id)
        )
        chunk_result = await db.execute(chunk_count_query)
        chunk_counts = dict(chunk_result.all())

        image_count_query = (
            select(DocumentImage.document_id, func.count(DocumentImage.id))
            .where(DocumentImage.document_id.in_(doc_ids))
            .group_by(DocumentImage.document_id)
        )
        image_result = await db.execute(image_count_query)
        image_counts = dict(image_result.all())

    doc_responses = []
    for doc in documents:
        doc_responses.append(
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                original_filename=doc.original_filename,
                file_size_bytes=doc.file_size_bytes,
                page_count=doc.page_count,
                status=doc.status.value,
                progress=doc.progress.value if doc.progress else None,
                images_progress=doc.images_progress.value
                if doc.images_progress
                else None,
                error_message=doc.error_message,
                chunk_count=chunk_counts.get(doc.id, 0),
                image_count=image_counts.get(doc.id, 0),
                tags=[TagResponse.model_validate(t) for t in doc.tags],
                created_at=doc.created_at,
                updated_at=doc.updated_at,
            )
        )

    return DocumentListResponse(documents=doc_responses, total=total)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(db: DBSession, document_id: uuid.UUID):
    """Get document details including chunk count and tags."""
    doc = await db.execute(
        select(Document)
        .options(selectinload(Document.tags))
        .where(Document.id == document_id)
    )
    doc = doc.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_count = (
        await db.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document_id
            )
        )
        or 0
    )

    image_count = (
        await db.scalar(
            select(func.count(DocumentImage.id)).where(
                DocumentImage.document_id == document_id
            )
        )
        or 0
    )

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        status=doc.status.value,
        progress=doc.progress.value if doc.progress else None,
        images_progress=doc.images_progress.value if doc.images_progress else None,
        error_message=doc.error_message,
        chunk_count=chunk_count,
        image_count=image_count,
        tags=[TagResponse.model_validate(t) for t in doc.tags],
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    db: DBSession, document_id: uuid.UUID, update: DocumentUpdate
):
    """Update document metadata."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.flush()

    # Re-fetch with tags
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.tags))
        .where(Document.id == document_id)
    )
    doc = result.scalar_one()

    chunk_count = (
        await db.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document_id
            )
        )
        or 0
    )

    image_count = (
        await db.scalar(
            select(func.count(DocumentImage.id)).where(
                DocumentImage.document_id == document_id
            )
        )
        or 0
    )

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        status=doc.status.value,
        progress=doc.progress.value if doc.progress else None,
        images_progress=doc.images_progress.value if doc.images_progress else None,
        error_message=doc.error_message,
        chunk_count=chunk_count,
        image_count=image_count,
        tags=[TagResponse.model_validate(t) for t in doc.tags],
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(db: DBSession, document_id: uuid.UUID):
    """Delete a document, all its chunks/images, and associated GCS files."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Clean up GCS files (original document + extracted images)
    try:
        from app.services.storage import delete_document_files

        deleted_count = await asyncio.to_thread(delete_document_files, document_id)
        logger.info(
            "Deleted %d GCS objects for document %s", deleted_count, document_id
        )
    except Exception:
        logger.warning(
            "Failed to delete GCS files for document %s (proceeding with DB delete)",
            document_id,
            exc_info=True,
        )

    await db.delete(doc)


@router.post("/{document_id}/tags", response_model=DocumentResponse)
async def add_tags_to_document(
    db: DBSession,
    space_id: uuid.UUID,
    document_id: uuid.UUID,
    body: DocumentTagsUpdate,
):
    """Add tags to a document."""
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.tags))
        .where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Fetch tags to add — validate each belongs to this space
    for tag_id in body.tag_ids:
        tag = await db.get(Tag, tag_id)
        if not tag:
            raise HTTPException(status_code=404, detail=f"Tag {tag_id} not found")
        if tag.space_id != space_id:
            raise HTTPException(
                status_code=400,
                detail=f"Tag {tag_id} does not belong to this space",
            )
        if tag not in doc.tags:
            doc.tags.append(tag)

    await db.flush()

    chunk_count = (
        await db.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document_id
            )
        )
        or 0
    )

    image_count = (
        await db.scalar(
            select(func.count(DocumentImage.id)).where(
                DocumentImage.document_id == document_id
            )
        )
        or 0
    )

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        status=doc.status.value,
        progress=doc.progress.value if doc.progress else None,
        images_progress=doc.images_progress.value if doc.images_progress else None,
        error_message=doc.error_message,
        chunk_count=chunk_count,
        image_count=image_count,
        tags=[TagResponse.model_validate(t) for t in doc.tags],
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.delete("/{document_id}/tags/{tag_id}", response_model=DocumentResponse)
async def remove_tag_from_document(
    db: DBSession,
    document_id: uuid.UUID,
    tag_id: uuid.UUID,
):
    """Remove a tag from a document."""
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.tags))
        .where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    tag = await db.get(Tag, tag_id)
    if tag and tag in doc.tags:
        doc.tags.remove(tag)

    await db.flush()

    chunk_count = (
        await db.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document_id
            )
        )
        or 0
    )

    image_count = (
        await db.scalar(
            select(func.count(DocumentImage.id)).where(
                DocumentImage.document_id == document_id
            )
        )
        or 0
    )

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        status=doc.status.value,
        progress=doc.progress.value if doc.progress else None,
        images_progress=doc.images_progress.value if doc.images_progress else None,
        error_message=doc.error_message,
        chunk_count=chunk_count,
        image_count=image_count,
        tags=[TagResponse.model_validate(t) for t in doc.tags],
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkResponse])
async def get_document_chunks(
    db: DBSession,
    document_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """View the chunks for a document (paginated)."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .offset(offset)
        .limit(limit)
    )
    chunks = result.scalars().all()

    return [DocumentChunkResponse.model_validate(c) for c in chunks]


@router.get("/{document_id}/images", response_model=list[DocumentImageResponse])
async def get_document_images(
    db: DBSession,
    document_id: uuid.UUID,
):
    """List all extracted images for a document."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        select(DocumentImage)
        .where(DocumentImage.document_id == document_id)
        .order_by(DocumentImage.image_index)
    )
    images = result.scalars().all()

    from app.services.storage import get_public_url

    return [
        DocumentImageResponse(
            id=img.id,
            gcs_url=get_public_url(img.gcs_uri),
            page_number=img.page_number,
            image_index=img.image_index,
            mime_type=img.mime_type,
            caption=img.caption,
            created_at=img.created_at,
        )
        for img in images
    ]
