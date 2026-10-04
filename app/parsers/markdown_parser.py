"""Markdown Parser with heading hierarchy tracking."""

import logging
import re
from typing import Any

import markdown
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension

from app.parsers.base import BoundingBox, DocumentParser, ParsedDocument, ParsedElement

logger = logging.getLogger(__name__)


class MarkdownParser(DocumentParser):
    """Markdown parser that tracks heading hierarchy and extracts structured content."""

    @property
    def supported_source_types(self) -> list[str]:
        return ["markdown", "text"]

    async def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        """
        Parse Markdown document.

        Extracts:
        - Text sections with heading hierarchy breadcrumbs
        - Code blocks preserved
        - Tables as markdown
        - Heading structure as hierarchy array
        """
        # Decode bytes to string
        try:
            content = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = file_bytes.decode("utf-8", errors="replace")

        elements: list[ParsedElement] = []
        lines = content.split("\n")

        # Track current heading hierarchy
        heading_stack: list[tuple[int, str]] = []  # (level, heading_text)

        # Current section being built
        current_section_lines: list[str] = []
        current_section_start_line = 0
        current_heading_hierarchy: list[str] = []

        def flush_current_section(line_num: int):
            """Flush accumulated section lines as a ParsedElement."""
            nonlocal current_section_lines, current_section_start_line, current_heading_hierarchy
            if current_section_lines:
                section_content = "\n".join(current_section_lines).strip()
                if section_content:
                    elements.append(ParsedElement(
                        content=section_content,
                        element_type="text",
                        page_number=1,  # Markdown is single "page"
                        bbox=None,  # No bbox for markdown
                        heading_hierarchy=current_heading_hierarchy.copy(),
                        metadata={
                            "start_line": current_section_start_line,
                            "end_line": line_num,
                        },
                    ))
                current_section_lines = []
                current_section_start_line = line_num + 1

        for line_num, line in enumerate(lines):
            # Check for heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                # Flush previous section before starting new heading
                flush_current_section(line_num)

                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()

                # Update heading stack
                # Pop headings of same or higher level
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()

                heading_stack.append((level, heading_text))
                current_heading_hierarchy = [h[1] for h in heading_stack]

                # Add heading as its own element
                elements.append(ParsedElement(
                    content=f"{'#' * level} {heading_text}",
                    element_type="heading",
                    page_number=1,
                    bbox=None,
                    heading_hierarchy=current_heading_hierarchy.copy(),
                    metadata={"heading_level": level},
                ))

                current_section_start_line = line_num + 1
            else:
                # Regular content line
                if not current_section_lines:
                    current_section_start_line = line_num
                current_section_lines.append(line)

        # Flush any remaining content
        flush_current_section(len(lines))

        return ParsedDocument(
            elements=elements,
            total_pages=1,  # Markdown treated as single page
            source_type="markdown",
            metadata={
                "filename": filename,
                "line_count": len(lines),
                "heading_count": sum(1 for e in elements if e.element_type == "heading"),
            },
        )