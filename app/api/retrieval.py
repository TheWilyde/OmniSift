"""Retrieval debug API routes for testing search quality and access boundaries."""

import time
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_async_session
from app.schemas.document import (
    RetrievalDebugRequest,
    RetrievalDebugResponse,
    RetrievalDebugParentChunk,
    MatchedChildChunk,
)
from app.schemas.auth import UserContext
from app.services.hybrid_search import HybridSearchService, get_hybrid_search_service
from app.services.embedding_service import create_embedding_provider

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


async def get_hybrid_search_dep(
    session: AsyncSession = Depends(get_async_session),
) -> HybridSearchService:
    """Dependency injection for HybridSearchService."""
    return await get_hybrid_search_service(session)


@router.post("/query", response_model=RetrievalDebugResponse)
async def retrieval_debug_query(
    request: RetrievalDebugRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    hybrid_search_service: HybridSearchService = Depends(get_hybrid_search_dep),
    x_impersonate_role: str = Header(None, alias="X-Impersonate-Role"),
) -> RetrievalDebugResponse:
    """
    Debug endpoint for retrieval pipeline testing.
    
    Executes the full hybrid search pipeline and returns detailed results
    for inspection without LLM generation overhead.
    
    Features:
    - Honors X-Impersonate-Role header in development mode
    - Returns re-ranked parent chunks with relevance scores
    - Includes matched child chunk coordinates (page, offsets, bbox)
    - Provides execution metrics (latency, match counts)
    
    Args:
        request: Query text and optional top_k, document_ids
        user: Current user context (from auth or impersonation)
        
    Returns:
        Structured retrieval results with debug information
    """
    total_start = time.perf_counter()
    
    # Get user roles (from auth context, including impersonation)
    user_roles = user.roles
    
    # Generate query embedding
    embedding_provider = create_embedding_provider()
    query_embedding = await embedding_provider.embed_text(request.query)
    
    # Execute hybrid search + re-ranking
    response = await hybrid_search_service.search_and_rerank(
        query_text=request.query,
        query_embedding=query_embedding,
        user_roles=user_roles,
        top_k=request.top_k * 4,  # Get more child chunks for better parent resolution
        document_ids=request.document_ids,
        rerank_top_k=request.top_k,
    )
    
    total_latency_ms = (time.perf_counter() - total_start) * 1000
    
    # Build debug parent chunks with document titles
    debug_parents = []
    for parent in response.resolved_parents:
        # Get document title
        from app.models.document import Document
        from sqlalchemy import select
        doc_query = select(Document.title).where(Document.id == parent.document_id)
        doc_result = await session.execute(doc_query)
        doc_title = doc_result.scalar_one_or_none() or "Unknown Document"
        
        debug_parents.append(
            RetrievalDebugParentChunk(
                id=parent.id,
                document_id=parent.document_id,
                document_title=doc_title,
                chunk_index=parent.chunk_index,
                content=parent.content,
                token_count=parent.token_count,
                page_start=parent.page_start,
                page_end=parent.page_end,
                heading_hierarchy=parent.heading_hierarchy,
                relevance_score=parent.relevance_score,
                max_fused_score=parent.max_fused_score,
                matched_children=parent.matched_children,
            )
        )
    
    return RetrievalDebugResponse(
        query=request.query,
        user_roles=user_roles,
        has_sufficient_context=response.has_sufficient_context,
        parent_chunks=debug_parents,
        metrics={
            "dense_match_count": response.dense_match_count,
            "sparse_match_count": response.sparse_match_count,
            "total_child_matches": response.total_child_matches,
            "unique_parent_count": response.unique_parent_count,
            "retrieval_latency_ms": round(response.retrieval_latency_ms, 2),
            "rerank_latency_ms": round(response.rerank_latency_ms, 2),
            "total_latency_ms": round(total_latency_ms, 2),
            "relevance_threshold": settings.relevance_score_threshold,
            "reranker_provider": settings.reranker_provider,
            "reranker_model": settings.reranker_model,
        }
    )


@router.get("/health")
async def retrieval_health() -> dict:
    """Health check for retrieval service."""
    return {
        "status": "healthy",
        "reranker_provider": settings.reranker_provider,
        "reranker_model": settings.reranker_model,
        "relevance_threshold": settings.relevance_score_threshold,
    }