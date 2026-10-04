"""Parser factory for selecting the appropriate parser."""

import logging
from typing import Optional

from app.parsers.base import DocumentParser, ParsedDocument
from app.parsers.pdf_parser import PDFParser
from app.parsers.markdown_parser import MarkdownParser

logger = logging.getLogger(__name__)


class ParserFactory:
    """Factory for creating and managing document parsers."""

    def __init__(self):
        self._parsers: list[DocumentParser] = [
            PDFParser(),
            MarkdownParser(),
        ]

    def get_parser(self, source_type: str) -> Optional[DocumentParser]:
        """Get a parser that can handle the given source type."""
        for parser in self._parsers:
            if parser.can_parse(source_type):
                return parser
        return None

    async def parse(self, source_type: str, file_bytes: bytes, filename: str) -> ParsedDocument:
        """
        Parse document using the appropriate parser.

        Args:
            source_type: Type of document (pdf, markdown, etc.)
            file_bytes: Raw file content
            filename: Original filename

        Returns:
            ParsedDocument with extracted elements

        Raises:
            ValueError: If no parser supports the source type
        """
        parser = self.get_parser(source_type)
        if parser is None:
            raise ValueError(f"No parser available for source type: {source_type}")

        logger.info(f"Parsing {filename} with {parser.__class__.__name__}")
        return await parser.parse(file_bytes, filename)

    def register_parser(self, parser: DocumentParser):
        """Register a new parser (added to front for priority)."""
        self._parsers.insert(0, parser)


# Global factory instance
parser_factory = ParserFactory()