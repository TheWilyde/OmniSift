"""Pydantic schemas for documents."""

import uuid
from datetime import datetime
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class DocumentBase(BaseModel):
    """Base document schema."""
    title: str = Field(..., max_length=512)
    source_type: str = Field(..., max_length=32)  # pdf, notion, markdown
    file_path: str = Field(..., max_length=1024)
    file_hash: str = Field(..., max_length=64)
    file_size_bytes: int = Field(..., gt=0)
    content_type: str = Field(..., max_length=128)
    allowed_roles: List[str] = Field(default_factory=lambda: ["general"])


class DocumentCreate(DocumentBase):
    """Schema for creating a document."""
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""
    title: Optional[str] = Field(None, max_length=512)
    source_type: Optional[str] = Field(None, max_length=32)
    status: Optional[str] = Field(None, max_length=32)
    allowed_roles: Optional[List[str]] = None
    doc_metadata: Optional[Dict[str, Any]] = None
    processed_at: Optional[datetime] = None


class DocumentResponse(DocumentBase):
    """Schema for document response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    duplicate: bool = False
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None


class DocumentListItem(DocumentResponse):
    """Schema for document list item with chunk counts."""
    parent_chunk_count: int = 0
    child_chunk_count: int = 0


class DocumentListResponse(BaseModel):
    """Schema for paginated document list response."""
    items: List[DocumentListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class DocumentChunkBase(BaseModel):
    """Base document chunk schema."""
    chunk_index: int = Field(..., ge=0)
    content: str
    token_count: int = Field(default=0, ge=0)
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentChunkCreate(DocumentChunkBase):
    """Schema for creating a document chunk."""
    document_id: uuid.UUID
    embedding: Optional[List[float]] = None


class DocumentChunkResponse(DocumentChunkBase):
    """Schema for document chunk response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    created_at: datetime


class DocumentChunkWithScore(DocumentChunkResponse):
    """Document chunk with similarity score."""
    similarity_score: float


class DocumentWithChunks(DocumentResponse):
    """Document with its chunks."""
    chunks: List[DocumentChunkResponse] = Field(default_factory=[])


class ParentChunkBase(BaseModel):
    """Base parent chunk schema."""
    chunk_index: int = Field(..., ge=0)
    content: str
    token_count: int = Field(default=0, ge=0)
    page_start: int = Field(..., ge=0)
    page_end: int = Field(..., ge=0)
    heading_hierarchy: List[str] = Field(default_factory=list)
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)


class ParentChunkCreate(ParentChunkBase):
    """Schema for creating a parent chunk."""
    document_id: uuid.UUID


class ParentChunkResponse(ParentChunkBase):
    """Schema for parent chunk response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    created_at: datetime


class ChildChunkBase(BaseModel):
    """Base child chunk schema."""
    chunk_index: int = Field(..., ge=0)
    content: str
    token_count: int = Field(default=0, ge=0)
    page_number: int = Field(..., ge=0)
    char_start: int = Field(..., ge=0)
    char_end: int = Field(..., ge=0)
    bbox: Optional[Dict[str, Any]] = None
    allowed_roles: List[str] = Field(default_factory=lambda: ["general"])
    embedding: Optional[List[float]] = None
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)


class ChildChunkCreate(ChildChunkBase):
    """Schema for creating a child chunk."""
    document_id: uuid.UUID
    parent_id: uuid.UUID


class ChildChunkResponse(ChildChunkBase):
    """Schema for child chunk response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    parent_id: uuid.UUID
    created_at: datetime


class DocumentSearchRequest(BaseModel):
    """Schema for document search request."""
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=10, ge=1, le=100)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    document_ids: Optional[List[uuid.UUID]] = None


class DocumentSearchResult(BaseModel):
    """Schema for document search result."""
    chunk: DocumentChunkWithScore
    document: DocumentResponse


class MatchedChildChunk(BaseModel):
    """Child chunk match with location info for citations and highlighting."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chunk_index: int
    page_number: int
    char_start: int
    char_end: int
    bbox: Optional[Dict[str, Any]] = None
    fused_score: float
    dense_rank: Optional[int] = None
    sparse_rank: Optional[int] = None


class ResolvedParentChunk(BaseModel):
    """Parent chunk with its matched child chunks for citation/highlighting."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int
    page_start: int
    page_end: int
    heading_hierarchy: List[str]
    matched_children: List[MatchedChildChunk]
    # Highest fused score among matched children for ranking
    max_fused_score: float
    # Cross-encoder relevance score (set after re-ranking)
    relevance_score: Optional[float] = None
    created_at: datetime


class HybridSearchResponse(BaseModel):
    """Hybrid search response with resolved parent chunks."""
    results: List[DocumentSearchResult]
    resolved_parents: List[ResolvedParentChunk]
    total_child_matches: int
    unique_parent_count: int
    # Confidence floor: true if at least one parent chunk meets minimum relevance
    has_sufficient_context: bool
    # Search execution metrics
    dense_match_count: int
    sparse_match_count: int
    retrieval_latency_ms: float
    rerank_latency_ms: float
    total_latency_ms: float


class RetrievalDebugRequest(BaseModel):
    """Request for retrieval debug endpoint."""
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=50)
    document_ids: Optional[List[uuid.UUID]] = None


class RetrievalDebugParentChunk(BaseModel):
    """Parent chunk info for debug response."""
    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    chunk_index: int
    content: str
    token_count: int
    page_start: int
    page_end: int
    heading_hierarchy: List[str]
    relevance_score: Optional[float] = None
    max_fused_score: float
    matched_children: List[MatchedChildChunk]


class RetrievalDebugResponse(BaseModel):
    """Structured response for retrieval debug endpoint."""
    query: str
    user_roles: List[str]
    has_sufficient_context: bool
    parent_chunks: List[RetrievalDebugParentChunk]
    metrics: Dict[str, Any]
