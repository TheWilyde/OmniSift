"""SQLAlchemy models for query telemetry and observability."""

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QueryLog(Base):
    """Query telemetry log for observability and cost tracking."""

    __tablename__ = "query_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    role: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    dense_matches_count: Mapped[int] = mapped_column(default=0)
    sparse_matches_count: Mapped[int] = mapped_column(default=0)
    relevance_scores: Mapped[List[float]] = mapped_column(
        ARRAY(Float), nullable=False, default=list
    )
    retrieval_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    rerank_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    generation_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    prompt_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    completion_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    has_sufficient_context: Mapped[bool] = mapped_column(default=False)
    finish_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_query_logs_created_at", "created_at"),
        Index("ix_query_logs_role_created", "role", "created_at"),
        Index("ix_query_logs_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<QueryLog(id={self.id}, role={self.role}, query={self.query_text[:50]}...)>"