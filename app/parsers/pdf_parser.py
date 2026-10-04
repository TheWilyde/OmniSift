"""PDF Parser using PyMuPDF (fitz)."""

import logging
from typing import Any

import pymupdf as fitz

from app.parsers.base import BoundingBox, DocumentParser, ParsedDocument, ParsedElement

logger = logging.getLogger(__name__)


class PDFParser(DocumentParser):
    """PDF parser that extracts text blocks, tables, and structure using PyMuPDF."""

    @property
    def supported_source_types(self) -> list[str]:
        return ["pdf"]

    async def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        """
        Parse PDF document.

        Extracts:
        - Text blocks with normalized bounding boxes
        - Tables as markdown
        - Page numbers (1-based)
        - Structural breaks between paragraphs and tables
        """
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        elements: list[ParsedElement] = []

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_number = page_num + 1  # 1-based
                page_width = page.rect.width
                page_height = page.rect.height

                # Extract text blocks with bounding boxes
                text_elements = self._extract_text_blocks(page, page_number, page_width, page_height)
                elements.extend(text_elements)

                # Extract tables
                table_elements = self._extract_tables(page, page_number, page_width, page_height)
                elements.extend(table_elements)

            return ParsedDocument(
                elements=elements,
                total_pages=len(doc),
                source_type="pdf",
                metadata={
                    "filename": filename,
                    "page_count": len(doc),
                },
            )
        finally:
            doc.close()

    def _extract_text_blocks(
        self, page: fitz.Page, page_number: int, page_width: float, page_height: float
    ) -> list[ParsedElement]:
        """Extract text blocks with normalized bounding boxes."""
        elements: list[ParsedElement] = []

        # Get text blocks with detailed info
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        for block in blocks:
            if block["type"] != 0:  # Only text blocks (type 0)
                continue

            # Combine all lines in the block
            block_text_parts = []
            block_bbox = None

            for line in block["lines"]:
                line_text = ""
                for span in line["spans"]:
                    line_text += span["text"]
                if line_text.strip():
                    block_text_parts.append(line_text.strip())

                # Track bbox for the block
                line_bbox = fitz.Rect(line["bbox"])
                if block_bbox is None:
                    block_bbox = line_bbox
                else:
                    block_bbox = block_bbox | line_bbox

            if not block_text_parts:
                continue

            content = "\n".join(block_text_parts).strip()
            if not content:
                continue

            # Normalize bounding box
            bbox = None
            if block_bbox:
                bbox = BoundingBox.from_absolute(
                    block_bbox.x0, block_bbox.y0, block_bbox.x1, block_bbox.y1,
                    page_width, page_height
                )

            elements.append(ParsedElement(
                content=content,
                element_type="text",
                page_number=page_number,
                bbox=bbox,
                metadata={"block_number": block.get("number", 0)},
            ))

        return elements

    def _extract_tables(
        self, page: fitz.Page, page_number: int, page_width: float, page_height: float
    ) -> list[ParsedElement]:
        """Extract tables from page and convert to markdown."""
        elements: list[ParsedElement] = []

        try:
            tabs = page.find_tables()
            for table_idx, table in enumerate(tabs):
                # Extract table as markdown
                markdown_table = table.to_markdown()
                if not markdown_table.strip():
                    continue

                # Get table bounding box
                bbox = table.bbox
                norm_bbox = BoundingBox.from_absolute(
                    bbox.x0, bbox.y0, bbox.x1, bbox.y1,
                    page_width, page_height
                )

                elements.append(ParsedElement(
                    content=markdown_table,
                    element_type="table",
                    page_number=page_number,
                    bbox=norm_bbox,
                    metadata={"table_index": table_idx},
                ))
        except Exception as e:
            logger.warning(f"Table extraction failed on page {page_number}: {e}")

        return elements
