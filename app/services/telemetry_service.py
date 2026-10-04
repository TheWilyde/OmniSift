"""Telemetry service for query logging and observability."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telemetry import QueryLog
from app.core.config import settings

logger = logging.getLogger(__name__)

# Gemini 3.8 Flash pricing (per 1M tokens)
GEMINI_38_FLASH_INPUT_COST_PER_M = 0.075   # $0.075 per 1M input tokens
GEMINI_38_FLASH_OUTPUT_COST_PER_M = 0.30   # $0.30 per 1M output tokens


class TelemetryService:
    """Service for logging query telemetry and computing aggregate metrics."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_query(
        self,
        user_id: Optional[UUID],
        role: Optional[str],
        query_text: str,
        dense_matches_count: int,
        sparse_matches_count: int,
        relevance_scores: List[float],
        retrieval_latency_ms: float,
        rerank_latency_ms: float,
        generation_latency_ms: float,
        total_latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        has_sufficient_context: bool,
        finish_reason: Optional[str] = None,
    ) -> QueryLog:
        """
        Log a query execution with full telemetry.
        
        Fire-and-forget: this is called after the response is complete.
        """
        # Calculate estimated cost using Gemini 3.8 Flash pricing
        input_cost = (prompt_tokens / 1_000_000) * GEMINI_38_FLASH_INPUT_COST_PER_M
        output_cost = (completion_tokens / 1_000_000) * GEMINI_38_FLASH_OUTPUT_COST_PER_M
        estimated_cost_usd = input_cost + output_cost

        query_log = QueryLog(
            user_id=user_id,
            role=role,
            query_text=query_text,
            dense_matches_count=dense_matches_count,
            sparse_matches_count=sparse_matches_count,
            relevance_scores=relevance_scores,
            retrieval_latency_ms=retrieval_latency_ms,
            rerank_latency_ms=rerank_latency_ms,
            generation_latency_ms=generation_latency_ms,
            total_latency_ms=total_latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=estimated_cost_usd,
            has_sufficient_context=has_sufficient_context,
            finish_reason=finish_reason,
            created_at=datetime.now(timezone.utc),
        )

        self.session.add(query_log)
        await self.session.flush()
        return query_log

    async def get_aggregate_metrics(
        self,
        hours: int = 24,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregate telemetry metrics for the specified time window.
        
        Args:
            hours: Time window in hours (default 24)
            role: Optional role filter
            
        Returns:
            Dictionary with aggregate metrics
        """
        from sqlalchemy import text as sql_text
        
        # Build base filter using make_interval for proper parameter binding
        base_filter = "WHERE created_at >= NOW() - make_interval(hours => :hours)"
        params = {"hours": hours}
        
        if role:
            base_filter += " AND role = :role"
            params["role"] = role

        # Total queries
        total_query = f"""
            SELECT COUNT(*) as total_queries
            FROM query_logs
            {base_filter}
        """
        total_result = await self.session.execute(text(total_query), params)
        total_queries = total_result.scalar() or 0

        if total_queries == 0:
            return {
                "total_queries": 0,
                "time_window_hours": hours,
                "latency": {
                    "retrieval_p50_ms": 0,
                    "retrieval_p95_ms": 0,
                    "rerank_p50_ms": 0,
                    "rerank_p95_ms": 0,
                    "generation_p50_ms": 0,
                    "generation_p95_ms": 0,
                    "total_p50_ms": 0,
                    "total_p95_ms": 0,
                },
                "tokens": {
                    "total_prompt_tokens": 0,
                    "total_completion_tokens": 0,
                    "avg_prompt_tokens": 0,
                    "avg_completion_tokens": 0,
                },
                "cost": {
                    "total_cost_usd": 0.0,
                    "avg_cost_per_query_usd": 0.0,
                },
                "context": {
                    "sufficient_context_rate": 0.0,
                    "blocked_by_confidence_floor": 0,
                    "blocked_by_rbac": 0,
                },
            }

        # Percentile latencies
        latency_query = f"""
            SELECT
                percentile_cont(0.50) WITHIN GROUP (ORDER BY retrieval_latency_ms) as retrieval_p50,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY retrieval_latency_ms) as retrieval_p95,
                percentile_cont(0.50) WITHIN GROUP (ORDER BY rerank_latency_ms) as rerank_p50,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY rerank_latency_ms) as rerank_p95,
                percentile_cont(0.50) WITHIN GROUP (ORDER BY generation_latency_ms) as generation_p50,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY generation_latency_ms) as generation_p95,
                percentile_cont(0.50) WITHIN GROUP (ORDER BY total_latency_ms) as total_p50,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY total_latency_ms) as total_p95
            FROM query_logs
            {base_filter}
        """
        latency_result = await self.session.execute(text(latency_query), params)
        latencies = latency_result.fetchone()

        # Token totals and averages
        token_query = f"""
            SELECT
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                AVG(prompt_tokens)::int as avg_prompt_tokens,
                AVG(completion_tokens)::int as avg_completion_tokens
            FROM query_logs
            {base_filter}
        """
        token_result = await self.session.execute(text(token_query), params)
        tokens = token_result.fetchone()

        # Cost totals
        cost_query = f"""
            SELECT
                SUM(estimated_cost_usd) as total_cost_usd,
                AVG(estimated_cost_usd) as avg_cost_per_query_usd
            FROM query_logs
            {base_filter}
        """
        cost_result = await self.session.execute(text(cost_query), params)
        costs = cost_result.fetchone()

        # Context metrics
        context_query = f"""
            SELECT
                COUNT(*) FILTER (WHERE has_sufficient_context = true)::float / COUNT(*) as sufficient_context_rate,
                COUNT(*) FILTER (WHERE has_sufficient_context = false AND dense_matches_count > 0) as blocked_by_confidence_floor,
                COUNT(*) FILTER (WHERE has_sufficient_context = false AND dense_matches_count = 0) as blocked_by_rbac
            FROM query_logs
            {base_filter}
        """
        context_result = await self.session.execute(text(context_query), params)
        context = context_result.fetchone()

        return {
            "total_queries": total_queries,
            "time_window_hours": hours,
            "latency": {
                "retrieval_p50_ms": round(float(latencies.retrieval_p50 or 0), 1),
                "retrieval_p95_ms": round(float(latencies.retrieval_p95 or 0), 1),
                "rerank_p50_ms": round(float(latencies.rerank_p50 or 0), 1),
                "rerank_p95_ms": round(float(latencies.rerank_p95 or 0), 1),
                "generation_p50_ms": round(float(latencies.generation_p50 or 0), 1),
                "generation_p95_ms": round(float(latencies.generation_p95 or 0), 1),
                "total_p50_ms": round(float(latencies.total_p50 or 0), 1),
                "total_p95_ms": round(float(latencies.total_p95 or 0), 1),
            },
            "tokens": {
                "total_prompt_tokens": int(tokens.total_prompt_tokens or 0),
                "total_completion_tokens": int(tokens.total_completion_tokens or 0),
                "avg_prompt_tokens": int(tokens.avg_prompt_tokens or 0),
                "avg_completion_tokens": int(tokens.avg_completion_tokens or 0),
            },
            "cost": {
                "total_cost_usd": round(float(costs.total_cost_usd or 0), 6),
                "avg_cost_per_query_usd": round(float(costs.avg_cost_per_query_usd or 0), 6),
            },
            "context": {
                "sufficient_context_rate": round(float(context.sufficient_context_rate or 0), 3),
                "blocked_by_confidence_floor": int(context.blocked_by_confidence_floor or 0),
                "blocked_by_rbac": int(context.blocked_by_rbac or 0),
            },
        }


async def log_query_async(
    user_id: Optional[UUID],
    role: Optional[str],
    query_text: str,
    dense_matches_count: int,
    sparse_matches_count: int,
    relevance_scores: List[float],
    retrieval_latency_ms: float,
    rerank_latency_ms: float,
    generation_latency_ms: float,
    total_latency_ms: float,
    prompt_tokens: int,
    completion_tokens: int,
    has_sufficient_context: bool,
    finish_reason: Optional[str] = None,
) -> None:
    """
    Fire-and-forget async query logging.
    
    Creates its own session to avoid blocking the main request.
    """
    from app.core.database import async_session_maker
    
    async with async_session_maker() as session:
        try:
            service = TelemetryService(session)
            await service.log_query(
                user_id=user_id,
                role=role,
                query_text=query_text,
                dense_matches_count=dense_matches_count,
                sparse_matches_count=sparse_matches_count,
                relevance_scores=relevance_scores,
                retrieval_latency_ms=retrieval_latency_ms,
                rerank_latency_ms=rerank_latency_ms,
                generation_latency_ms=generation_latency_ms,
                total_latency_ms=total_latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                has_sufficient_context=has_sufficient_context,
                finish_reason=finish_reason,
            )
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to log query telemetry: {e}")
            await session.rollback()