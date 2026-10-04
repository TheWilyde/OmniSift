"""Chat streaming API endpoint with SSE protocol."""

import json
import time
import uuid
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse

from app.api.deps import get_current_user, optional_impersonation
from app.schemas.document import HybridSearchResponse
from app.services.hybrid_search import get_hybrid_search_service_global as get_hybrid_search_service
from app.services.embedding_service import create_embedding_provider
from app.services.llm_service import get_llm_service, LLMStreamChunk
from app.services.prompt_service import (
    build_messages,
    validate_context_sufficiency,
    INSUFFICIENT_CONTEXT_MESSAGE,
)
from app.core.config import settings

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """Single chat message in history."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatStreamRequest(BaseModel):
    """Request body for streaming chat."""
    message: str = Field(..., min_length=1, max_length=8000)
    history: List[ChatMessage] = Field(default_factory=list, max_length=20)
    top_k: int = Field(default=5, ge=1, le=20)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=8192)


class SourceItem(BaseModel):
    """Source item for metadata event."""
    source_id: str
    document_title: str
    page_start: int
    page_end: int
    preview: str
    child_bboxes: List[dict] = Field(default_factory=list)


class MetadataEvent(BaseModel):
    """Metadata event payload (Stage 1)."""
    query: str
    user_roles: List[str]
    has_sufficient_context: bool
    retrieval_metrics: dict
    sources: List[SourceItem]


class DoneEvent(BaseModel):
    """Completion event payload (Stage 3)."""
    generation_metrics: dict
    finish_reason: str


def format_sse_event(event_type: str, data: dict) -> str:
    """Format an SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_chat_response(
    request: Request,
    query: str,
    user_roles: List[str],
    history: List[ChatMessage],
    top_k: int,
    temperature: Optional[float],
    max_tokens: Optional[int],
) -> AsyncGenerator[str, None]:
    """
    Generator that yields SSE events for the chat stream.
    
    Event sequence:
    1. metadata - retrieval stats and source info
    2. text - token deltas
    3. done - generation metrics
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.perf_counter()
    
    try:
        # Step A: Run hybrid retrieval + re-ranking
        # First generate query embedding
        embedding_provider = create_embedding_provider()
        query_embedding = await embedding_provider.embed_text(query)
        
        hybrid_service = await get_hybrid_search_service()
        search_response: HybridSearchResponse = await hybrid_service.search_and_rerank(
            query_text=query,
            query_embedding=query_embedding,
            user_roles=user_roles,
            top_k=top_k * 4,  # Get more child chunks for better parent resolution
            rerank_top_k=top_k,
        )
        
        retrieval_latency = (time.perf_counter() - start_time) * 1000
        
        # Check context sufficiency
        should_generate, refusal_msg = validate_context_sufficiency(search_response.has_sufficient_context)
        
        # Build source items for metadata event
        sources = []
        for parent in search_response.resolved_parents:
            child_bboxes = []
            for child in parent.matched_children:
                if child.bbox:
                    child_bboxes.append({
                        "page": child.page_number,
                        "x0": child.bbox.x0,
                        "y0": child.bbox.y0,
                        "x1": child.bbox.x1,
                        "y1": child.bbox.y1,
                    })
            
            sources.append(SourceItem(
                source_id=str(parent.id),
                document_title=parent.document_title,
                page_start=parent.page_start,
                page_end=parent.page_end,
                preview=parent.content[:300] + "..." if len(parent.content) > 300 else parent.content,
                child_bboxes=child_bboxes,
            ))
        
        # Stage 1: Emit metadata event
        metadata = MetadataEvent(
            query=query,
            user_roles=user_roles,
            has_sufficient_context=search_response.has_sufficient_context,
            retrieval_metrics={
                "dense_matches": search_response.dense_match_count,
                "sparse_matches": search_response.sparse_match_count,
                "total_child_matches": search_response.total_child_matches,
                "retrieval_latency_ms": round(retrieval_latency, 1),
                "rerank_latency_ms": round(search_response.rerank_latency_ms, 1),
                "relevance_threshold": search_response.relevance_threshold,
            },
            sources=sources,
        )
        
        yield format_sse_event("metadata", metadata.model_dump())
        
        if not should_generate:
            # Stream refusal message as text event
            yield format_sse_event("text", {"delta": refusal_msg})
            
            # Stage 3: Done event
            done = DoneEvent(
                generation_metrics={
                    "generation_latency_ms": 0,
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                },
                finish_reason="insufficient_context",
            )
            yield format_sse_event("done", done.model_dump())
            return
        
        # Step C: Build prompt and stream LLM
        history_dicts = [{"role": m.role, "content": m.content} for m in history]
        messages = build_messages(query, search_response.resolved_parents, history_dicts)
        
        llm_service = get_llm_service()
        gen_start = time.perf_counter()
        
        accumulated_text = ""
        prompt_tokens = 0
        completion_tokens = 0
        
        async for chunk in llm_service.stream_chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            # Check for client disconnect
            if await request.is_disconnected():
                break
            
            if chunk.delta:
                accumulated_text += chunk.delta
                # Stage 2: Emit token delta
                yield format_sse_event("text", {"delta": chunk.delta})
            
            if chunk.finish_reason:
                if chunk.usage:
                    prompt_tokens = chunk.usage.get("prompt_tokens", 0)
                    completion_tokens = chunk.usage.get("completion_tokens", 0)
                break
        
        generation_latency = (time.perf_counter() - gen_start) * 1000
        
        # Stage 3: Emit done event
        done = DoneEvent(
            generation_metrics={
                "generation_latency_ms": round(generation_latency, 1),
                "total_tokens": prompt_tokens + completion_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            finish_reason=chunk.finish_reason if 'chunk' in dir() else "completed",
        )
        yield format_sse_event("done", done.model_dump())
        
    except Exception as e:
        # Error event
        yield format_sse_event("error", {"error": str(e), "request_id": request_id})


@router.post("/stream")
async def chat_stream(
    request: Request,
    body: ChatStreamRequest,
    current_user: dict = Depends(get_current_user),
    impersonated_roles: Optional[List[str]] = Depends(optional_impersonation),
):
    """
    Stream chat response with SSE protocol.
    
    Event stream contract:
    1. event: metadata - Retrieval stats and source info (emitted immediately)
    2. event: text - Token deltas (incremental)
    3. event: done - Generation metrics (on completion)
    4. event: error - Error info (on failure)
    """
    # Determine effective roles (impersonation takes precedence in dev)
    if impersonated_roles is not None:
        user_roles = impersonated_roles
    else:
        user_roles = current_user.get("roles", ["general"])
    
    return EventSourceResponse(
        stream_chat_response(
            request=request,
            query=body.message,
            user_roles=user_roles,
            history=body.history,
            top_k=body.top_k,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/complete")
async def chat_complete(
    body: ChatStreamRequest,
    current_user: dict = Depends(get_current_user),
    impersonated_roles: Optional[List[str]] = Depends(optional_impersonation),
):
    """
    Non-streaming chat completion for testing.
    Returns full response with citations and metadata.
    """
    if impersonated_roles is not None:
        user_roles = impersonated_roles
    else:
        user_roles = current_user.get("roles", ["general"])
    
    # Run retrieval
    # First generate query embedding
    embedding_provider = create_embedding_provider()
    query_embedding = await embedding_provider.embed_text(body.message)
    
    hybrid_service = await get_hybrid_search_service()
    search_response = await hybrid_service.search_and_rerank(
        query_text=body.message,
        query_embedding=query_embedding,
        user_roles=user_roles,
        top_k=body.top_k * 4,
        rerank_top_k=body.top_k,
    )
    
    should_generate, refusal_msg = validate_context_sufficiency(search_response.has_sufficient_context)
    
    if not should_generate:
        return {
            "response": refusal_msg,
            "has_sufficient_context": False,
            "citations": [],
            "retrieval_metrics": {
                "dense_matches": search_response.dense_match_count,
                "sparse_matches": search_response.sparse_match_count,
                "total_child_matches": search_response.total_child_matches,
            },
        }
    
    # Generate response
    history_dicts = [{"role": m.role, "content": m.content} for m in body.history]
    messages = build_messages(body.message, search_response.resolved_parents, history_dicts)
    
    llm_service = get_llm_service()
    response_text, metrics = await llm_service.generate_chat(
        messages=messages,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    
    # Build citations from parent chunks
    citations = [
        {
            "source_id": str(parent.id),
            "document_title": parent.document_title,
            "page_start": parent.page_start,
            "page_end": parent.page_end,
            "relevance_score": parent.relevance_score,
        }
        for parent in search_response.resolved_parents
    ]
    
    return {
        "response": response_text,
        "has_sufficient_context": True,
        "citations": citations,
        "retrieval_metrics": {
            "dense_matches": search_response.dense_match_count,
            "sparse_matches": search_response.sparse_match_count,
            "total_child_matches": search_response.total_child_matches,
        },
        "generation_metrics": {
            "latency_ms": metrics.latency_ms,
            "prompt_tokens": metrics.prompt_tokens,
            "completion_tokens": metrics.completion_tokens,
            "total_tokens": metrics.total_tokens,
            "finish_reason": metrics.finish_reason,
        },
    }