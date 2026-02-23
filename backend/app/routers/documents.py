"""Document management router.

Handles file uploads, document CRUD, tagging, and chunk viewing.
PDFs are processed entirely in memory — no files are saved to disk.
"""

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
    DocumentStatus,
    Space,
    Tag,
    document_tags,
)
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentTagsUpdate,
    DocumentUpdate,
    TagResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/spaces/{space_id}/documents", tags=["documents"])


async def _run_ingestion_pipeline(document_id: uuid.UUID, pdf_bytes: bytes) -> None:
    """Background task: parse PDF from bytes, chunk, embed, update document status.

    This runs outside the request lifecycle with its own DB session.
    """
    from app.database import async_session_factory
    from app.services.chunker import chunk_pages
    from app.services.embeddings import embed_texts
    from app.services.pdf_parser import parse_pdf

    async with async_session_factory() as db:
        try:
            doc = await db.get(Document, document_id)
            if not doc:
                logger.error(f"Document {document_id} not found for ingestion")
                return

            # Step 1: Parse PDF from bytes (no disk I/O)
            logger.info(f"Parsing PDF: {doc.original_filename}")
            parsed = parse_pdf(pdf_bytes)
            doc.page_count = parsed.page_count

            # Step 2: Chunk the parsed pages
            logger.info(f"Chunking document into semantic chunks")
            chunks = chunk_pages(
                parsed.pages,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )

            if not chunks:
                doc.status = DocumentStatus.FAILED
                doc.error_message = "No text content could be extracted from the PDF."
                await db.commit()
                return

            # Step 3: Embed all chunks
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            chunk_texts = [c.content for c in chunks]
            embeddings = await embed_texts(chunk_texts)

            # Step 4: Store chunks in DB
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

            doc.status = DocumentStatus.READY
            await db.commit()
            logger.info(
                f"Ingestion complete: {doc.original_filename} ({len(chunks)} chunks)"
            )

        except Exception as e:
            logger.exception(f"Ingestion failed for document {document_id}: {e}")
            doc = await db.get(Document, document_id)
            if doc:
                doc.status = DocumentStatus.FAILED
                doc.error_message = str(e)[:1000]
                await db.commit()


@router.post("/", response_model=DocumentResponse, status_code=201)
async def upload_document(
    db: DBSession,
    background_tasks: BackgroundTasks,
    space_id: uuid.UUID,
    file: UploadFile,
    course_name: str | None = Query(None),
    subject: str | None = Query(None),
):
    """Upload a PDF document and start the ingestion pipeline.

    The document will be processed entirely in memory (no files saved to disk):
    1. PDF text extraction
    2. Semantic chunking
    3. Embedding generation
    4. Storage in vector database

    Check the document's `status` field to track progress:
    - `processing`: Ingestion is in progress
    - `ready`: Document is fully indexed and searchable
    - `failed`: An error occurred (see `error_message`)
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    if file.size and file.size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB.",
        )

    # Read file into memory
    pdf_bytes = await file.read()
    file_size = len(pdf_bytes)

    # Validate space exists
    space = await db.get(Space, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")

    # Create document record (no file_path needed)
    doc = Document(
        filename=f"{uuid.uuid4()}.pdf",
        original_filename=file.filename,
        file_path="",  # no disk storage
        file_size_bytes=file_size,
        course_name=course_name,
        subject=subject,
        space_id=space_id,
        status=DocumentStatus.PROCESSING,
    )
    db.add(doc)
    await db.commit()

    # Kick off background ingestion with in-memory bytes
    background_tasks.add_task(_run_ingestion_pipeline, doc.id, pdf_bytes)

    # Return response with chunk_count=0 since processing hasn't started
    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        course_name=doc.course_name,
        subject=doc.subject,
        status=doc.status.value,
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
    course_name: str | None = Query(None),
    subject: str | None = Query(None),
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

    if course_name:
        query = query.where(Document.course_name.ilike(f"{course_name}%"))
    if subject:
        query = query.where(Document.subject.ilike(f"{subject}%"))
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
    if doc_ids:
        chunk_count_query = (
            select(DocumentChunk.document_id, func.count(DocumentChunk.id))
            .where(DocumentChunk.document_id.in_(doc_ids))
            .group_by(DocumentChunk.document_id)
        )
        chunk_result = await db.execute(chunk_count_query)
        chunk_counts = dict(chunk_result.all())

    doc_responses = []
    for doc in documents:
        doc_responses.append(
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                original_filename=doc.original_filename,
                file_size_bytes=doc.file_size_bytes,
                page_count=doc.page_count,
                course_name=doc.course_name,
                subject=doc.subject,
                status=doc.status.value,
                error_message=doc.error_message,
                chunk_count=chunk_counts.get(doc.id, 0),
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

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        course_name=doc.course_name,
        subject=doc.subject,
        status=doc.status.value,
        error_message=doc.error_message,
        chunk_count=chunk_count,
        tags=[TagResponse.model_validate(t) for t in doc.tags],
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    db: DBSession, document_id: uuid.UUID, update: DocumentUpdate
):
    """Update document metadata (course name, subject)."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if update.course_name is not None:
        doc.course_name = update.course_name
    if update.subject is not None:
        doc.subject = update.subject

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

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        course_name=doc.course_name,
        subject=doc.subject,
        status=doc.status.value,
        error_message=doc.error_message,
        chunk_count=chunk_count,
        tags=[TagResponse.model_validate(t) for t in doc.tags],
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(db: DBSession, document_id: uuid.UUID):
    """Delete a document and all its chunks and embeddings."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.delete(doc)


@router.post("/{document_id}/tags", response_model=DocumentResponse)
async def add_tags_to_document(
    db: DBSession,
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

    # Fetch tags to add
    for tag_id in body.tag_ids:
        tag = await db.get(Tag, tag_id)
        if not tag:
            raise HTTPException(status_code=404, detail=f"Tag {tag_id} not found")
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

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        course_name=doc.course_name,
        subject=doc.subject,
        status=doc.status.value,
        error_message=doc.error_message,
        chunk_count=chunk_count,
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

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        course_name=doc.course_name,
        subject=doc.subject,
        status=doc.status.value,
        error_message=doc.error_message,
        chunk_count=chunk_count,
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
