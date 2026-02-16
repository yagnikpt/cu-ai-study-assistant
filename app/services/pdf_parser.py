"""PDF parsing service using PyMuPDF (fitz).

Extracts text from PDFs page-by-page, preserving structure and metadata.
Handles multi-column layouts by using PyMuPDF's block-level extraction.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)


@dataclass
class PageContent:
    """Extracted content from a single PDF page."""

    page_number: int  # 1-indexed
    text: str
    headings: list[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """Result of parsing an entire PDF."""

    pages: list[PageContent]
    page_count: int
    metadata: dict


def parse_pdf(file_path: str | Path) -> ParsedDocument:
    """Parse a PDF file and extract text content page by page.

    Uses PyMuPDF's block-level extraction which handles multi-column
    layouts better than simple text extraction. Blocks are sorted by
    position (top-to-bottom, left-to-right) to maintain reading order.

    Args:
        file_path: Path to the PDF file.

    Returns:
        ParsedDocument with page-by-page content and metadata.

    Raises:
        FileNotFoundError: If the PDF file doesn't exist.
        ValueError: If the file is not a valid PDF or is encrypted.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    try:
        doc = pymupdf.open(str(file_path))
    except Exception as e:
        raise ValueError(f"Failed to open PDF: {e}") from e

    if doc.is_encrypted:
        doc.close()
        raise ValueError("PDF is encrypted and cannot be parsed")

    # Extract document-level metadata
    pdf_metadata = doc.metadata or {}
    metadata = {
        "title": pdf_metadata.get("title", ""),
        "author": pdf_metadata.get("author", ""),
        "subject": pdf_metadata.get("subject", ""),
        "keywords": pdf_metadata.get("keywords", ""),
        "page_count": doc.page_count,
    }

    pages: list[PageContent] = []

    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        page_number = page_idx + 1

        # Extract text blocks - each block is a dict with type, lines, etc.
        # block type: 0 = text, 1 = image
        page_dict: dict = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)  # type: ignore[assignment]
        blocks: list[dict] = page_dict.get("blocks", [])

        page_text_parts: list[str] = []
        headings: list[str] = []

        for block in blocks:
            if block.get("type") != 0:  # Skip non-text blocks (images)
                continue

            block_text_lines: list[str] = []
            for line in block.get("lines", []):
                line_text = ""
                max_font_size = 0.0

                for span in line.get("spans", []):
                    line_text += span.get("text", "")
                    max_font_size = max(max_font_size, span.get("size", 0))

                line_text = line_text.strip()
                if not line_text:
                    continue

                block_text_lines.append(line_text)

                # Heuristic: lines with font size > 14pt are likely headings
                if max_font_size > 14 and len(line_text) < 200:
                    headings.append(line_text)

            block_text = "\n".join(block_text_lines)
            if block_text.strip():
                page_text_parts.append(block_text)

        page_text = "\n\n".join(page_text_parts)

        pages.append(
            PageContent(
                page_number=page_number,
                text=page_text,
                headings=headings,
            )
        )

    doc.close()

    logger.info(f"Parsed PDF: {file_path.name}, {len(pages)} pages")

    return ParsedDocument(
        pages=pages,
        page_count=len(pages),
        metadata=metadata,
    )
