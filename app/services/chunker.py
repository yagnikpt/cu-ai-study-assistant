"""Semantic chunking service.

Splits parsed document pages into semantically meaningful chunks,
preserving context boundaries (paragraphs, sections) rather than
using naive fixed-size sliding windows.
"""

import logging
import re
from dataclasses import dataclass, field

from app.services.pdf_parser import PageContent

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A semantically coherent text chunk with source metadata."""

    content: str
    chunk_index: int
    page_start: int  # 1-indexed
    page_end: int  # 1-indexed
    section_title: str | None = None
    token_count: int = 0
    metadata: dict = field(default_factory=dict)


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate (~0.75 words per token for English)."""
    return int(len(text.split()) / 0.75)


def _split_into_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs by double newlines or significant breaks."""
    # Split on double newlines (paragraph breaks)
    paragraphs = re.split(r"\n{2,}", text)
    # Filter out empty/whitespace-only paragraphs
    return [p.strip() for p in paragraphs if p.strip()]


def _find_section_title(text: str, page_headings: list[str]) -> str | None:
    """Find the most relevant section heading for a chunk of text.

    Returns the last heading that appears before or within the chunk text.
    """
    for heading in reversed(page_headings):
        if heading in text or len(heading) < 100:
            return heading
    return page_headings[0] if page_headings else None


def chunk_pages(
    pages: list[PageContent],
    chunk_size: int = 700,
    chunk_overlap: int = 100,
) -> list[Chunk]:
    """Split document pages into semantically meaningful chunks.

    Strategy:
    1. Collect paragraphs from each page, tracking which page they came from.
    2. Group paragraphs into chunks that respect:
       - Paragraph boundaries (never split mid-paragraph if possible)
       - Target chunk size (in estimated tokens)
       - Section/heading boundaries (prefer to start new chunks at headings)
    3. Add overlap between chunks to preserve context at boundaries.

    Args:
        pages: List of PageContent from PDF parsing.
        chunk_size: Target chunk size in estimated tokens.
        chunk_overlap: Overlap between consecutive chunks in estimated tokens.

    Returns:
        List of Chunk objects with content and source metadata.
    """
    if not pages:
        return []

    # Step 1: Build a flat list of (paragraph_text, page_number, is_heading, headings)
    @dataclass
    class ParagraphInfo:
        text: str
        page_number: int
        is_heading: bool
        page_headings: list[str]

    all_paragraphs: list[ParagraphInfo] = []

    for page in pages:
        if not page.text.strip():
            continue

        paragraphs = _split_into_paragraphs(page.text)
        for para in paragraphs:
            is_heading = para in page.headings
            all_paragraphs.append(
                ParagraphInfo(
                    text=para,
                    page_number=page.page_number,
                    is_heading=is_heading,
                    page_headings=page.headings,
                )
            )

    if not all_paragraphs:
        return []

    # Step 2: Group paragraphs into chunks
    chunks: list[Chunk] = []
    current_paragraphs: list[ParagraphInfo] = []
    current_tokens = 0
    current_section: str | None = None
    chunk_index = 0

    def _flush_chunk() -> None:
        nonlocal chunk_index, current_paragraphs, current_tokens, current_section

        if not current_paragraphs:
            return

        content = "\n\n".join(p.text for p in current_paragraphs)
        page_start = current_paragraphs[0].page_number
        page_end = current_paragraphs[-1].page_number

        chunks.append(
            Chunk(
                content=content,
                chunk_index=chunk_index,
                page_start=page_start,
                page_end=page_end,
                section_title=current_section,
                token_count=_estimate_tokens(content),
                metadata={
                    "page_range": f"{page_start}-{page_end}",
                    "paragraph_count": len(current_paragraphs),
                },
            )
        )
        chunk_index += 1

        # Keep overlap: find paragraphs whose combined tokens are <= chunk_overlap
        overlap_paragraphs: list[ParagraphInfo] = []
        overlap_tokens = 0
        for p in reversed(current_paragraphs):
            p_tokens = _estimate_tokens(p.text)
            if overlap_tokens + p_tokens > chunk_overlap:
                break
            overlap_paragraphs.insert(0, p)
            overlap_tokens += p_tokens

        current_paragraphs = overlap_paragraphs
        current_tokens = overlap_tokens

    for para_info in all_paragraphs:
        para_tokens = _estimate_tokens(para_info.text)

        # If this paragraph is a heading, it may signal a section break.
        # Start a new chunk if current chunk has meaningful content.
        if para_info.is_heading and current_tokens > chunk_overlap:
            _flush_chunk()
            current_section = para_info.text

        # Track the current section title
        if para_info.is_heading:
            current_section = para_info.text

        # If adding this paragraph would exceed chunk_size and we have content,
        # flush the current chunk first.
        if current_tokens + para_tokens > chunk_size and current_paragraphs:
            _flush_chunk()

        current_paragraphs.append(para_info)
        current_tokens += para_tokens

    # Flush remaining content
    _flush_chunk()

    logger.info(f"Created {len(chunks)} chunks from {len(pages)} pages")
    return chunks
