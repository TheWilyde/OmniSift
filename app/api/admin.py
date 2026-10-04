"""Admin API endpoints for metrics and observability."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_async_session
from app.models.telemetry import QueryLog
from app.schemas.auth import UserContext
from app.services.telemetry_service import TelemetryService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics")
async def get_metrics(
    hours: int = Query(default=24, ge=1, le=168, description="Time window in hours (1-168)"),
    role: Optional[str] = Query(default=None, description="Filter by role"),
    current_user: UserContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get aggregate telemetry metrics.
    
    Requires admin role.
    
    Returns:
        - Total queries in time window
        - P50/P95 latency breakdown (retrieval, rerank, generation, total)
        - Token usage and cost totals/averages
        - Context sufficiency rates and block rates
    """
    service = TelemetryService(session)
    metrics = await service.get_aggregate_metrics(hours=hours, role=role)
    return metrics


@router.get("/query-logs")
async def get_query_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    hours: int = Query(default=24, ge=1, le=168),
    role: Optional[str] = Query(default=None),
    current_user: UserContext = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get recent query logs for detailed inspection.
    
    Requires admin role.
    """
    query = select(QueryLog).where(
        QueryLog.created_at >= func.now() - text(f"INTERVAL '{hours} hours'")
    )
    
    if role:
        query = query.where(QueryLog.role == role)
    
    query = query.order_by(desc(QueryLog.created_at)).limit(limit).offset(offset)
    
    result = await session.execute(query)
    logs = result.scalars().all()
    
    return {
        "logs": [
            {
                "id": str(log.id),
                "user_id": str(log.user_id) if log.user_id else None,
                "role": log.role,
                "query_text": log.query_text,
                "dense_matches_count": log.dense_matches_count,
                "sparse_matches_count": log.sparse_matches_count,
                "relevance_scores": log.relevance_scores,
                "retrieval_latency_ms": log.retrieval_latency_ms,
                "rerank_latency_ms": log.rerank_latency_ms,
                "generation_latency_ms": log.generation_latency_ms,
                "total_latency_ms": log.total_latency_ms,
                "prompt_tokens": log.prompt_tokens,
                "completion_tokens": log.completion_tokens,
                "estimated_cost_usd": log.estimated_cost_usd,
                "has_sufficient_context": log.has_sufficient_context,
                "finish_reason": log.finish_reason,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/health")
async def admin_health():
    """Simple admin health check."""
    return {"status": "ok", "service": "admin"}