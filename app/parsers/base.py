"""Base parser interface and shared data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BoundingBox:
    """Normalized bounding box coordinates (0.0 to 1.0)."""
    x0: float  # Left
    y0: float  # Top
    x1: float  # Right
    y1: float  # Bottom

    def to_dict(self) -> dict[str, float]:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}

    @classmethod
    def from_absolute(
        cls, abs_x0: float, abs_y0: float, abs_x1: float, abs_y1: float,
        page_width: float, page_height: float
    ) -> "BoundingBox":
        """Create normalized bbox from absolute coordinates."""
        return cls(
            x0=abs_x0 / page_width if page_width > 0 else 0.0,
            y0=abs_y0 / page_height if page_height > 0 else 0.0,
            x1=abs_x1 / page_width if page_width > 0 else 0.0,
            y1=abs_y1 / page_height if page_height > 0 else 0.0,
        )


@dataclass
class ParsedElement:
    """A single parsed element (text block, table, etc.) from a document."""
    content: str
    element_type: str  # "text", "table", "heading", etc.
    page_number: int  # 1-based page number
    bbox: Optional[BoundingBox] = None
    heading_hierarchy: list[str] = field(default_factory=list)  # e.g., ["Security Policies", "Data Retention"]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "element_type": self.element_type,
            "page_number": self.page_number,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "heading_hierarchy": self.heading_hierarchy,
            "metadata": self.metadata,
        }


@dataclass
class ParsedDocument:
    """Result of parsing a document."""
    elements: list[ParsedElement]
    total_pages: int
    source_type: str  # "pdf", "markdown", "notion", etc.
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_text_content(self) -> str:
        """Get full text content of all elements."""
        return "\n\n".join(e.content for e in self.elements if e.content.strip())


class DocumentParser(ABC):
    """Abstract base class for document parsers."""

    @property
    @abstractmethod
    def supported_source_types(self) -> list[str]:
        """List of source types this parser can handle."""
        pass

    @abstractmethod
    async def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        """
        Parse document from bytes.

        Args:
            file_bytes: Raw file content
            filename: Original filename for context

        Returns:
            ParsedDocument with elements, page count, and metadata
        """
        pass

    def can_parse(self, source_type: str) -> bool:
        """Check if this parser can handle the given source type."""
        return source_type in self.supported_source_types