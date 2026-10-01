"""SQLAlchemy models for documents, parent chunks, and child chunks."""

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Computed,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base


class Document(Base):
    """Document model for storing raw file metadata."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # pdf, notion, markdown
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)  # MinIO object key
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)  # SHA-256
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    allowed_roles: Mapped[List[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )  # PostgreSQL array for role-based access
    doc_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=lambda: {})
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="uploaded", index=True
    )  # uploaded, processing, processed, failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    parent_chunks: Mapped[List["ParentChunk"]] = relationship(
        "ParentChunk", back_populates="document", cascade="all, delete-orphan"
    )
    child_chunks: Mapped[List["ChildChunk"]] = relationship(
        "ChildChunk", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_documents_status_created", "status", "created_at"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_file_hash", "file_hash", unique=True),
        Index("ix_documents_allowed_roles", "allowed_roles", postgresql_using="gin"),
        Index("ix_documents_source_type", "source_type"),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title={self.title}, source_type={self.source_type})>"


class ParentChunk(Base):
    """Parent chunk model for larger semantic sections (800-1200 tokens)."""

    __tablename__ = "parent_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # 800-1200 token range
    token_count: Mapped[int] = mapped_column(nullable=False, default=0)
    page_start: Mapped[int] = mapped_column(nullable=False)
    page_end: Mapped[int] = mapped_column(nullable=False)
    heading_hierarchy: Mapped[List[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )  # Array of heading strings for hierarchy
    chunk_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=lambda: {})
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="parent_chunks")
    child_chunks: Mapped[List["ChildChunk"]] = relationship(
        "ChildChunk", back_populates="parent", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_parent_chunk_index"),
        Index("ix_parent_chunks_document_id", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<ParentChunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"


class ChildChunk(Base):
    """Child chunk model for smaller retrieval units (200-300 tokens) with embeddings."""

    __tablename__ = "child_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parent_chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # 200-300 token range
    token_count: Mapped[int] = mapped_column(nullable=False, default=0)
    page_number: Mapped[int] = mapped_column(nullable=False)
    char_start: Mapped[int] = mapped_column(nullable=False)
    char_end: Mapped[int] = mapped_column(nullable=False)
    bbox: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # {x0, y0, x1, y1} for visual highlights
    allowed_roles: Mapped[List[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )  # Denormalized for fast single-table filtering
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536), nullable=True  # 1536 for OpenAI text-embedding-3-small, adjust as needed
    )
    # Computed full-text search column
    tsv_content: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
        nullable=False,
    )
    chunk_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=lambda: {})
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    parent: Mapped["ParentChunk"] = relationship("ParentChunk", back_populates="child_chunks")
    document: Mapped["Document"] = relationship("Document", back_populates="child_chunks")

    __table_args__ = (
        UniqueConstraint("parent_id", "chunk_index", name="uq_child_chunk_index"),
        Index("ix_child_chunks_parent_id", "parent_id"),
        Index("ix_child_chunks_document_id", "document_id"),
        Index("ix_child_chunks_allowed_roles", "allowed_roles", postgresql_using="gin"),
        # HNSW cosine index for vector similarity search
        Index(
            "ix_child_chunks_embedding_hnsw_cosine",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # GIN index for full-text search
        Index("ix_child_chunks_tsv_content", "tsv_content", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<ChildChunk(id={self.id}, parent_id={self.parent_id}, index={self.chunk_index})>"