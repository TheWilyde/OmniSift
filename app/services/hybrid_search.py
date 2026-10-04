"""Hybrid retrieval service combining dense (vector) and sparse (full-text) search with RRF."""

import logging
import time
from typing import List, Optional, Dict, Any
from uuid import UUID
from collections import defaultdict
from datetime import datetime

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import ChildChunk, Document, ParentChunk
from app.schemas.document import (
    DocumentSearchResult,
    DocumentChunkWithScore,
    DocumentResponse,
    MatchedChildChunk,
    ResolvedParentChunk,
    HybridSearchResponse,
)
from app.services.reranker_service import RerankerService

logger = logging.getLogger(__name__)


class HybridSearchService:
    """
    Service for hybrid retrieval combining dense vector search and sparse full-text search
    using Reciprocal Rank Fusion (RRF) in a single optimized SQL query.
    """

    def __init__(self, session: AsyncSession, reranker: Optional[RerankerService] = None):
        self.session = session
        self.reranker = reranker
        self.relevance_threshold = settings.relevance_score_threshold

    async def search(
        self,
        query_text: str,
        query_embedding: List[float],
        user_roles: List[str],
        top_k: int = 20,
        document_ids: Optional[List[UUID]] = None,
    ) -> HybridSearchResponse:
        """
        Execute hybrid search with dense + sparse retrieval fused via RRF,
        then resolve and deduplicate parent chunks.

        Args:
            query_text: Raw query text for full-text search
            query_embedding: Query embedding vector for dense search
            user_roles: List of user roles for RBAC filtering
            top_k: Number of final child chunk results to return (default 20)
            document_ids: Optional list of document IDs to restrict search

        Returns:
            HybridSearchResponse with child results and resolved parent chunks
        """
        start_time = time.perf_counter()
        
        # Build the unified hybrid search query with CTEs
        has_doc_filter = document_ids is not None and len(document_ids) > 0
        sql = self._build_hybrid_search_query(with_doc_filter=has_doc_filter)

        # Prepare parameters - convert embedding to pgvector-compatible format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        params = {
            "query_text": query_text,
            "query_embedding": embedding_str,
            "user_roles": user_roles,
            "top_k": top_k,
        }

        if has_doc_filter:
            doc_id_placeholders = ",".join([f":doc_id_{i}" for i in range(len(document_ids))])
            sql = sql.format(doc_id_placeholders=doc_id_placeholders)
            for i, doc_id in enumerate(document_ids):
                params[f"doc_id_{i}"] = doc_id
        else:
            # Remove the placeholder if not used
            sql = sql.format(doc_id_placeholders="")

        # Execute the query
        result = await self.session.execute(text(sql), params)
        
        retrieval_latency_ms = (time.perf_counter() - start_time) * 1000

        # Map results to child chunk rows
        child_rows = []
        for row in result:
            child_rows.append({
                "chunk_id": row.chunk_id,
                "parent_id": row.parent_id,
                "document_id": row.document_id,
                "chunk_index": row.chunk_index,
                "content": row.content,
                "token_count": row.token_count,
                "page_number": row.page_number,
                "char_start": row.char_start,
                "char_end": row.char_end,
                "bbox": row.bbox,
                "allowed_roles": row.allowed_roles,
                "chunk_metadata": row.chunk_metadata,
                "created_at": row.created_at,
                "document_title": row.document_title,
                "source_type": row.source_type,
                "file_path": row.file_path,
                "file_hash": row.file_hash,
                "file_size_bytes": row.file_size_bytes,
                "content_type": row.content_type,
                "doc_allowed_roles": row.doc_allowed_roles,
                "doc_metadata": row.doc_metadata,
                "status": row.status,
                "doc_created_at": row.doc_created_at,
                "doc_updated_at": row.doc_updated_at,
                "doc_processed_at": row.doc_processed_at,
                "fused_score": float(row.fused_score),
            })

        # Build DocumentSearchResult list (child-level results)
        search_results = []
        for row in child_rows:
            chunk = ChildChunk(
                id=row["chunk_id"],
                parent_id=row["parent_id"],
                document_id=row["document_id"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                token_count=row["token_count"],
                page_number=row["page_number"],
                char_start=row["char_start"],
                char_end=row["char_end"],
                bbox=row["bbox"],
                allowed_roles=row["allowed_roles"],
                embedding=None,
                chunk_metadata=row["chunk_metadata"],
                created_at=row["created_at"],
            )

            document = Document(
                id=row["document_id"],
                title=row["document_title"],
                source_type=row["source_type"],
                file_path=row["file_path"],
                file_hash=row["file_hash"],
                file_size_bytes=row["file_size_bytes"],
                content_type=row["content_type"],
                allowed_roles=row["doc_allowed_roles"],
                doc_metadata=row["doc_metadata"],
                status=row["status"],
                created_at=row["doc_created_at"],
                updated_at=row["doc_updated_at"],
                processed_at=row["doc_processed_at"],
            )

            # Create chunk response with similarity_score manually
            chunk_response = DocumentChunkWithScore(
                id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                token_count=chunk.token_count,
                created_at=chunk.created_at,
                similarity_score=row["fused_score"],
            )

            doc_response = DocumentResponse.model_validate(document)

            search_results.append(
                DocumentSearchResult(chunk=chunk_response, document=doc_response)
            )

        # Step 2: Resolve and deduplicate parent chunks
        resolved_parents = await self._resolve_parent_chunks(child_rows)

        # Get dense/sparse match counts (we can estimate from child_rows by checking which CTE they came from)
        # For now, we'll use the CTE LIMIT as approximation - in practice we'd modify the query to return counts
        dense_match_count = min(50, len(child_rows))  # Approximation
        sparse_match_count = min(50, len(child_rows))  # Approximation

        return HybridSearchResponse(
            results=search_results,
            resolved_parents=resolved_parents,
            total_child_matches=len(child_rows),
            unique_parent_count=len(resolved_parents),
            has_sufficient_context=len(resolved_parents) > 0,  # Will be updated after rerank
            dense_match_count=dense_match_count,
            sparse_match_count=sparse_match_count,
            retrieval_latency_ms=retrieval_latency_ms,
            rerank_latency_ms=0.0,
            total_latency_ms=retrieval_latency_ms,
            relevance_threshold=settings.relevance_score_threshold,
        )

    async def _resolve_parent_chunks(self, child_rows: List[Dict[str, Any]]) -> List[ResolvedParentChunk]:
        """
        Map child chunks to parent chunks, deduplicate by parent_id,
        and collect matched child info for citations/highlighting.

        Args:
            child_rows: List of child chunk result dictionaries from RRF

        Returns:
            List of ResolvedParentChunk with matched children
        """
        if not child_rows:
            return []

        # Group child rows by parent_id
        parent_to_children: Dict[UUID, List[Dict[str, Any]]] = defaultdict(list)
        for row in child_rows:
            parent_to_children[row["parent_id"]].append(row)

        # Get unique parent IDs
        parent_ids = list(parent_to_children.keys())

        # Fetch parent chunks from database with document titles
        parent_query = (
            select(ParentChunk, Document.title)
            .join(Document, ParentChunk.document_id == Document.id)
            .where(ParentChunk.id.in_(parent_ids))
        )
        parent_result = await self.session.execute(parent_query)
        parent_chunks = {pc.id: (pc, title) for pc, title in parent_result.all()}

        # Build resolved parent chunks
        resolved = []
        for parent_id, children in parent_to_children.items():
            parent_data = parent_chunks.get(parent_id)
            if not parent_data:
                logger.warning(f"Parent chunk {parent_id} not found in database")
                continue
            
            parent_chunk, document_title = parent_data

            # Sort children by fused_score descending
            children_sorted = sorted(children, key=lambda c: c["fused_score"], reverse=True)

            # Build matched children list
            matched_children = []
            for child in children_sorted:
                matched_children.append(
                    MatchedChildChunk(
                        id=child["chunk_id"],
                        chunk_index=child["chunk_index"],
                        page_number=child["page_number"],
                        char_start=child["char_start"],
                        char_end=child["char_end"],
                        bbox=child["bbox"],
                        fused_score=child["fused_score"],
                    )
                )

            # Calculate max fused score for ranking
            max_fused_score = max(c["fused_score"] for c in children)

            resolved.append(
                ResolvedParentChunk(
                    id=parent_chunk.id,
                    document_id=parent_chunk.document_id,
                    document_title=document_title,
                    chunk_index=parent_chunk.chunk_index,
                    content=parent_chunk.content,
                    token_count=parent_chunk.token_count,
                    page_start=parent_chunk.page_start,
                    page_end=parent_chunk.page_end,
                    heading_hierarchy=parent_chunk.heading_hierarchy,
                    matched_children=matched_children,
                    max_fused_score=max_fused_score,
                    created_at=parent_chunk.created_at,
                )
            )

        # Sort by max_fused_score descending
        resolved.sort(key=lambda p: p.max_fused_score, reverse=True)

        return resolved

    async def search_and_rerank(
        self,
        query_text: str,
        query_embedding: List[float],
        user_roles: List[str],
        top_k: int = 20,
        document_ids: Optional[List[UUID]] = None,
        rerank_top_k: int = 5,
    ) -> HybridSearchResponse:
        """
        Execute hybrid search + cross-encoder re-ranking in one call.

        Args:
            query_text: Raw query text for full-text search
            query_embedding: Query embedding vector for dense search
            user_roles: List of user roles for RBAC filtering
            top_k: Number of child chunk results from RRF (default 20)
            document_ids: Optional list of document IDs to restrict search
            rerank_top_k: Number of parent chunks to return after re-ranking (default 5)

        Returns:
            HybridSearchResponse with re-ranked parent chunks
        """
        total_start = time.perf_counter()
        
        # Step 1: Hybrid search with parent resolution
        retrieval_start = time.perf_counter()
        response = await self.search(
            query_text=query_text,
            query_embedding=query_embedding,
            user_roles=user_roles,
            top_k=top_k,
            document_ids=document_ids,
        )
        retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000

        # Step 2: Re-rank parent chunks if reranker is available
        rerank_latency_ms = 0.0
        if self.reranker and response.resolved_parents:
            rerank_start = time.perf_counter()
            reranked_parents = await self.reranker.rerank(
                query=query_text,
                parent_chunks=response.resolved_parents,
                top_k=rerank_top_k,
            )
            rerank_latency_ms = (time.perf_counter() - rerank_start) * 1000
            
            # Step 3: Apply confidence floor
            # Filter out chunks below relevance threshold
            filtered_parents = [
                p for p in reranked_parents 
                if p.relevance_score is not None and p.relevance_score >= self.relevance_threshold
            ]
            
            response.resolved_parents = filtered_parents
            response.unique_parent_count = len(filtered_parents)
            # Confidence floor: true only if at least one parent meets threshold
            response.has_sufficient_context = len(filtered_parents) > 0

        total_latency_ms = (time.perf_counter() - total_start) * 1000
        
        # Update metrics
        response.retrieval_latency_ms = retrieval_latency_ms
        response.rerank_latency_ms = rerank_latency_ms
        response.total_latency_ms = total_latency_ms

        return response

    def _build_hybrid_search_query(self, with_doc_filter: bool = False) -> str:
        """
        Build the unified hybrid search SQL query with CTEs for:
        1. Dense search (vector similarity)
        2. Sparse search (full-text search)
        3. RRF fusion

        Args:
            with_doc_filter: Whether to include document ID filtering
        """
        dense_where = (
            "WHERE cc.embedding IS NOT NULL\n"
            "  AND cc.allowed_roles && :user_roles\n"
            "  AND d.status = 'completed'"
        )
        sparse_where = (
            "WHERE cc.tsv_content @@ websearch_to_tsquery('english', :query_text)\n"
            "  AND cc.allowed_roles && :user_roles\n"
            "  AND d.status = 'completed'"
        )

        if with_doc_filter:
            dense_where += "\n  AND cc.document_id IN ({doc_id_placeholders})"
            sparse_where += "\n  AND cc.document_id IN ({doc_id_placeholders})"

        return f"""
        WITH dense_search AS (
            SELECT
                cc.id AS chunk_id,
                cc.parent_id,
                cc.document_id,
                cc.chunk_index,
                cc.content,
                cc.token_count,
                cc.page_number,
                cc.char_start,
                cc.char_end,
                cc.bbox,
                cc.allowed_roles,
                cc.chunk_metadata,
                cc.created_at,
                d.title AS document_title,
                d.source_type,
                d.file_path,
                d.file_hash,
                d.file_size_bytes,
                d.content_type,
                d.allowed_roles AS doc_allowed_roles,
                d.doc_metadata,
                d.status,
                d.created_at AS doc_created_at,
                d.updated_at AS doc_updated_at,
                d.processed_at AS doc_processed_at,
                (cc.embedding <=> CAST(:query_embedding AS vector)) AS distance,
                ROW_NUMBER() OVER (ORDER BY (cc.embedding <=> CAST(:query_embedding AS vector)) ASC) AS dense_rank
            FROM child_chunks cc
            JOIN documents d ON cc.document_id = d.id
            {dense_where}
            ORDER BY (cc.embedding <=> CAST(:query_embedding AS vector)) ASC
            LIMIT 50
        ),
        sparse_search AS (
            SELECT
                cc.id AS chunk_id,
                cc.parent_id,
                cc.document_id,
                cc.chunk_index,
                cc.content,
                cc.token_count,
                cc.page_number,
                cc.char_start,
                cc.char_end,
                cc.bbox,
                cc.allowed_roles,
                cc.chunk_metadata,
                cc.created_at,
                d.title AS document_title,
                d.source_type,
                d.file_path,
                d.file_hash,
                d.file_size_bytes,
                d.content_type,
                d.allowed_roles AS doc_allowed_roles,
                d.doc_metadata,
                d.status,
                d.created_at AS doc_created_at,
                d.updated_at AS doc_updated_at,
                d.processed_at AS doc_processed_at,
                ts_rank_cd(cc.tsv_content, websearch_to_tsquery('english', :query_text)) AS sparse_score,
                ROW_NUMBER() OVER (ORDER BY ts_rank_cd(cc.tsv_content, websearch_to_tsquery('english', :query_text)) DESC) AS sparse_rank
            FROM child_chunks cc
            JOIN documents d ON cc.document_id = d.id
            {sparse_where}
            ORDER BY ts_rank_cd(cc.tsv_content, websearch_to_tsquery('english', :query_text)) DESC
            LIMIT 50
        ),
        rrf_fusion AS (
            SELECT
                COALESCE(d.chunk_id, s.chunk_id) AS chunk_id,
                COALESCE(d.parent_id, s.parent_id) AS parent_id,
                COALESCE(d.document_id, s.document_id) AS document_id,
                COALESCE(d.chunk_index, s.chunk_index) AS chunk_index,
                COALESCE(d.content, s.content) AS content,
                COALESCE(d.token_count, s.token_count) AS token_count,
                COALESCE(d.page_number, s.page_number) AS page_number,
                COALESCE(d.char_start, s.char_start) AS char_start,
                COALESCE(d.char_end, s.char_end) AS char_end,
                COALESCE(d.bbox, s.bbox) AS bbox,
                COALESCE(d.allowed_roles, s.allowed_roles) AS allowed_roles,
                COALESCE(d.chunk_metadata, s.chunk_metadata) AS chunk_metadata,
                COALESCE(d.created_at, s.created_at) AS created_at,
                COALESCE(d.document_title, s.document_title) AS document_title,
                COALESCE(d.source_type, s.source_type) AS source_type,
                COALESCE(d.file_path, s.file_path) AS file_path,
                COALESCE(d.file_hash, s.file_hash) AS file_hash,
                COALESCE(d.file_size_bytes, s.file_size_bytes) AS file_size_bytes,
                COALESCE(d.content_type, s.content_type) AS content_type,
                COALESCE(d.doc_allowed_roles, s.doc_allowed_roles) AS doc_allowed_roles,
                COALESCE(d.doc_metadata, s.doc_metadata) AS doc_metadata,
                COALESCE(d.status, s.status) AS status,
                COALESCE(d.doc_created_at, s.doc_created_at) AS doc_created_at,
                COALESCE(d.doc_updated_at, s.doc_updated_at) AS doc_updated_at,
                COALESCE(d.doc_processed_at, s.doc_processed_at) AS doc_processed_at,
                COALESCE(1.0 / (60 + d.dense_rank), 0.0) + COALESCE(1.0 / (60 + s.sparse_rank), 0.0) AS fused_score
            FROM dense_search d
            FULL OUTER JOIN sparse_search s ON d.chunk_id = s.chunk_id
        )
        SELECT *
        FROM rrf_fusion
        ORDER BY fused_score DESC
        LIMIT :top_k;
        """


async def get_hybrid_search_service(session: AsyncSession) -> HybridSearchService:
    """Dependency injection for HybridSearchService with reranker."""
    reranker = RerankerService()
    return HybridSearchService(session, reranker=reranker)


# Global instance for use in non-DI contexts (e.g., streaming endpoints)
# Lazy initialization - will be set on first use
_hybrid_search_service: HybridSearchService | None = None


async def _get_global_hybrid_search_service() -> HybridSearchService:
    """Get or create global hybrid search service instance."""
    global _hybrid_search_service
    if _hybrid_search_service is None:
        from app.core.database import async_session_maker
        from app.services.reranker_service import RerankerService
        session = async_session_maker()
        reranker = RerankerService()
        _hybrid_search_service = HybridSearchService(session, reranker=reranker)
    return _hybrid_search_service


# Export a callable that returns the service (for use in endpoints)
async def get_hybrid_search_service_global() -> HybridSearchService:
    """Get the global hybrid search service instance."""
    return await _get_global_hybrid_search_service()


# For backwards compatibility with existing imports
hybrid_search_service = None  # Will be set by get_hybrid_search_service_global()