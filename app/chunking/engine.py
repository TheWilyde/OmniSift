"""Parent-Child chunking engine with token-aware splitting."""

from dataclasses import dataclass
from typing import Any, Optional

from app.chunking.tokenizer import count_tokens, encode_text, decode_tokens
from app.parsers.base import ParsedDocument, ParsedElement


@dataclass
class ParentChunkData:
    """Data for a parent chunk to be persisted."""
    chunk_index: int
    content: str
    token_count: int
    page_start: int
    page_end: int
    heading_hierarchy: list[str]
    metadata: dict[str, Any]


@dataclass
class ChildChunkData:
    """Data for a child chunk to be persisted."""
    chunk_index: int
    content: str
    token_count: int
    page_number: int
    char_start: int
    char_end: int
    bbox: Optional[dict[str, float]]
    allowed_roles: list[str]
    metadata: dict[str, Any]


class ChunkingEngine:
    """
    Token-aware parent-child chunking engine.

    Parent chunks: 800-1200 tokens (for LLM context)
    Child chunks: 200-300 tokens with 30-token overlap (for embedding/search)
    """

    def __init__(
        self,
        parent_min_tokens: int = 800,
        parent_max_tokens: int = 1200,
        child_min_tokens: int = 200,
        child_max_tokens: int = 300,
        child_overlap_tokens: int = 30,
    ):
        self.parent_min_tokens = parent_min_tokens
        self.parent_max_tokens = parent_max_tokens
        self.child_min_tokens = child_min_tokens
        self.child_max_tokens = child_max_tokens
        self.child_overlap_tokens = child_overlap_tokens

    def chunk_document(
        self,
        parsed_doc: ParsedDocument,
        document_allowed_roles: list[str],
    ) -> tuple[list[ParentChunkData], list[ChildChunkData]]:
        """
        Chunk a parsed document into parent and child chunks.

        Returns:
            Tuple of (parent_chunks, child_chunks)
        """
        text_stream, position_map = self._build_text_stream(parsed_doc)
        parent_chunks = self._generate_parent_chunks(text_stream, position_map)
        child_chunks = self._generate_child_chunks(
            parent_chunks, text_stream, position_map, document_allowed_roles
        )
        return parent_chunks, child_chunks

    def _build_text_stream(
        self, parsed_doc: ParsedDocument
    ) -> tuple[str, list[dict[str, Any]]]:
        """Build continuous text stream with position mapping."""
        text_parts = []
        position_map = []
        char_offset = 0

        for elem_idx, element in enumerate(parsed_doc.elements):
            if not element.content.strip():
                continue

            content = element.content
            text_parts.append(content)

            for char_idx, _ in enumerate(content):
                position_map.append({
                    "char_offset": char_offset + char_idx,
                    "page_number": element.page_number,
                    "element_index": elem_idx,
                    "bbox": element.bbox.to_dict() if element.bbox else None,
                    "heading_hierarchy": element.heading_hierarchy,
                    "element_type": element.element_type,
                })

            char_offset += len(content)
            if elem_idx < len(parsed_doc.elements) - 1:
                text_parts.append("\n\n")
                char_offset += 2

        full_text = "".join(text_parts)
        return full_text, position_map

    def _generate_parent_chunks(
        self, text_stream: str, position_map: list[dict[str, Any]]
    ) -> list[ParentChunkData]:
        """Generate parent chunks (800-1200 tokens) from text stream."""
        parent_chunks: list[ParentChunkData] = []
        tokens = encode_text(text_stream)

        if not tokens:
            return parent_chunks

        chunk_index = 0
        token_start = 0

        while token_start < len(tokens):
            token_end = min(token_start + self.parent_max_tokens, len(tokens))

            if token_end - token_start < self.parent_min_tokens and token_end < len(tokens):
                token_end = min(token_start + self.parent_min_tokens, len(tokens))

            chunk_tokens = tokens[token_start:token_end]
            chunk_text = decode_tokens(chunk_tokens)

            char_start = self._find_char_position(text_stream, token_start, position_map)
            char_end = self._find_char_position(text_stream, token_end, position_map)

            page_start, page_end = self._get_page_range(position_map, char_start, char_end)
            heading_hierarchy = self._get_dominant_hierarchy(position_map, char_start, char_end)

            parent_chunks.append(ParentChunkData(
                chunk_index=chunk_index,
                content=chunk_text,
                token_count=len(chunk_tokens),
                page_start=page_start,
                page_end=page_end,
                heading_hierarchy=heading_hierarchy,
                metadata={},
            ))

            chunk_index += 1
            token_start = token_end

        return parent_chunks

    def _generate_child_chunks(
        self,
        parent_chunks: list[ParentChunkData],
        text_stream: str,
        position_map: list[dict[str, Any]],
        document_allowed_roles: list[str],
    ) -> list[ChildChunkData]:
        """Generate child chunks (200-300 tokens with overlap) from parent chunks."""
        child_chunks: list[ChildChunkData] = []
        global_child_index = 0

        for parent_idx, parent in enumerate(parent_chunks):
            parent_tokens = encode_text(parent.content)
            child_token_start = 0
            parent_token_len = len(parent_tokens)

            while child_token_start < parent_token_len:
                child_token_end = min(
                    child_token_start + self.child_max_tokens,
                    parent_token_len
                )

                if (child_token_end - child_token_start < self.child_min_tokens
                        and child_token_end < parent_token_len):
                    child_token_end = min(
                        child_token_start + self.child_min_tokens,
                        parent_token_len
                    )

                child_tokens = parent_tokens[child_token_start:child_token_end]
                child_text = decode_tokens(child_tokens)

                parent_start_in_stream = text_stream.find(parent.content)
                if parent_start_in_stream == -1:
                    parent_start_in_stream = 0

                prefix_tokens = encode_text(text_stream[:parent_start_in_stream])
                global_token_start = len(prefix_tokens) + child_token_start
                global_token_end = len(prefix_tokens) + child_token_end

                char_start = self._find_char_position(text_stream, global_token_start, position_map)
                char_end = self._find_char_position(text_stream, global_token_end, position_map)

                page_number = self._get_page_at_position(position_map, char_start)
                bbox = self._get_bbox_at_position(position_map, char_start)

                child_chunks.append(ChildChunkData(
                    chunk_index=global_child_index,
                    content=child_text,
                    token_count=len(child_tokens),
                    page_number=page_number,
                    char_start=char_start,
                    char_end=char_end,
                    bbox=bbox,
                    allowed_roles=document_allowed_roles,
                    metadata={"parent_chunk_index": parent_idx},
                ))

                global_child_index += 1

                # Overlap only when another window remains. For short parent
                # chunks, subtracting the overlap from the final end can move
                # the cursor backwards and loop forever.
                if child_token_end >= parent_token_len:
                    break
                child_token_start = max(
                    child_token_start + 1,
                    child_token_end - self.child_overlap_tokens,
                )

        return child_chunks

    def _find_char_position(
        self, text: str, token_index: int, position_map: list[dict[str, Any]]
    ) -> int:
        """Find character offset corresponding to a token index."""
        if token_index <= 0:
            return 0
        tokens = encode_text(text)
        if token_index >= len(tokens):
            return len(text)

        prefix_text = decode_tokens(tokens[:token_index])
        return len(prefix_text)

    def _get_page_range(
        self, position_map: list[dict[str, Any]], char_start: int, char_end: int
    ) -> tuple[int, int]:
        """Get start and end page numbers for a character range."""
        if not position_map:
            return 1, 1

        start_page = position_map[min(char_start, len(position_map) - 1)]["page_number"]
        end_page = position_map[min(char_end, len(position_map) - 1)]["page_number"]
        return start_page, end_page

    def _get_dominant_hierarchy(
        self, position_map: list[dict[str, Any]], char_start: int, char_end: int
    ) -> list[str]:
        """Get the most common heading hierarchy in a character range."""
        if not position_map:
            return []

        start_idx = min(char_start, len(position_map) - 1)
        end_idx = min(char_end, len(position_map) - 1)

        from collections import Counter
        hierarchies = []
        for i in range(start_idx, end_idx + 1):
            hier = position_map[i].get("heading_hierarchy", [])
            if hier:
                hierarchies.append(tuple(hier))

        if not hierarchies:
            return []

        most_common = Counter(hierarchies).most_common(1)[0][0]
        return list(most_common)

    def _get_page_at_position(
        self, position_map: list[dict[str, Any]], char_offset: int
    ) -> int:
        """Get page number at a character offset."""
        if not position_map:
            return 1
        idx = min(char_offset, len(position_map) - 1)
        return position_map[idx]["page_number"]

    def _get_bbox_at_position(
        self, position_map: list[dict[str, Any]], char_offset: int
    ) -> Optional[dict[str, float]]:
        """Get bounding box at a character offset."""
        if not position_map:
            return None
        idx = min(char_offset, len(position_map) - 1)
        return position_map[idx].get("bbox")
