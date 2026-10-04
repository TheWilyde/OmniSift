"""Transactional ingestion pipeline: parse → chunk → embed → persist."""

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document, ParentChunk, ChildChunk
from app.parsers import parser_factory, ParsedDocument
from app.chunking import ChunkingEngine, ParentChunkData, ChildChunkData
from app.services.embedding_service import create_embedding_provider, EmbeddingProvider

if TYPE_CHECKING:
    from app.services.document_service import DocumentIngestionService

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates the full document ingestion pipeline with transactional persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.chunking_engine = ChunkingEngine(
            parent_min_tokens=800,
            parent_max_tokens=1200,
            child_min_tokens=200,
            child_max_tokens=300,
            child_overlap_tokens=30,
        )
        self.embedding_provider: EmbeddingProvider = create_embedding_provider()

    async def process_document(
        self,
        document_id: UUID,
        file_bytes: bytes,
        filename: str,
        source_type: str,
        allowed_roles: list[str],
    ) -> Document:
        """
        Process a document through the full ingestion pipeline.

        Flow:
        1. Parse document (PDF/Markdown)
        2. Generate parent & child chunks
        3. Generate embeddings for child chunks
        4. Persist everything in a single transaction
        5. Update document status

        On any failure: set status to 'failed' and rollback.
        """
        document = await self._get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        try:
            # Step 1: Parse document
            logger.info(f"Parsing document {document_id} ({source_type})")
            parsed_doc = await parser_factory.parse(source_type, file_bytes, filename)

            # Step 2: Generate chunks
            logger.info(f"Chunking document {document_id}")
            parent_chunks, child_chunks = self.chunking_engine.chunk_document(
                parsed_doc, allowed_roles
            )

            # Step 3: Generate embeddings for child chunks
            logger.info(f"Generating embeddings for {len(child_chunks)} child chunks")
            child_chunks = await self._generate_embeddings(child_chunks)

            # Step 4: Persist in transaction
            logger.info(f"Persisting chunks for document {document_id}")
            await self._persist_chunks(document_id, parent_chunks, child_chunks)

            # Step 5: Update document status to completed
            document.status = "completed"
            from datetime import datetime, timezone
            document.processed_at = datetime.now(timezone.utc)
            await self.session.commit()

            logger.info(f"Document {document_id} ingestion completed successfully")
            return document

        except Exception as e:
            # Rollback and mark as failed
            await self.session.rollback()
            # rollback expires ORM state; load the document again before
            # updating it to avoid implicit async IO from attribute access.
            document = await self._get_document(document_id)
            if document is None:
                raise ValueError(f"Document {document_id} not found after ingestion failure") from e
            document.status = "failed"
            document.doc_metadata = {
                **(document.doc_metadata or {}),
                "ingestion_error": str(e),
            }
            await self.session.commit()
            logger.error(f"Document {document_id} ingestion failed: {e}")
            raise

    async def _get_document(self, document_id: UUID) -> Document | None:
        """Fetch document by ID."""
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def _generate_embeddings(self, child_chunks: list[ChildChunkData]) -> list[ChildChunkData]:
        """Generate embeddings for all child chunks in batches."""
        if not child_chunks:
            return child_chunks

        texts = [chunk.content for chunk in child_chunks]
        batch_size = self.embedding_provider.max_batch_size

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = await self.embedding_provider.embed_texts(batch)
            all_embeddings.extend(embeddings)

        # Attach embeddings to child chunks
        for chunk, embedding in zip(child_chunks, all_embeddings):
            chunk.embedding = embedding  # type: ignore[attr-defined]

        return child_chunks

    async def _persist_chunks(
        self,
        document_id: UUID,
        parent_chunks: list[ParentChunkData],
        child_chunks: list[ChildChunkData],
    ):
        """Bulk insert parent and child chunks in a single transaction."""
        # Insert parent chunks first
        parent_orm_objects: list[ParentChunk] = []
        for pc in parent_chunks:
            parent_orm = ParentChunk(
                document_id=document_id,
                chunk_index=pc.chunk_index,
                content=pc.content,
                token_count=pc.token_count,
                page_start=pc.page_start,
                page_end=pc.page_end,
                heading_hierarchy=pc.heading_hierarchy,
                chunk_metadata=pc.metadata,
            )
            self.session.add(parent_orm)
            parent_orm_objects.append(parent_orm)

        # Flush to get parent IDs
        await self.session.flush()

        # Map parent chunk_index to parent ID
        parent_id_map = {p.chunk_index: p.id for p in parent_orm_objects}

        # Insert child chunks with parent_id references
        for cc in child_chunks:
            parent_idx = cc.metadata.get("parent_chunk_index", 0)
            parent_id = parent_id_map.get(parent_idx)

            if parent_id is None:
                logger.warning(f"No parent found for child chunk {cc.chunk_index}, using first parent")
                parent_id = parent_orm_objects[0].id if parent_orm_objects else None

            child_orm = ChildChunk(
                parent_id=parent_id,
                document_id=document_id,
                chunk_index=cc.chunk_index,
                content=cc.content,
                token_count=cc.token_count,
                page_number=cc.page_number,
                char_start=cc.char_start,
                char_end=cc.char_end,
                bbox=cc.bbox,
                allowed_roles=cc.allowed_roles,
                embedding=cc.embedding,  # type: ignore[attr-defined]
                chunk_metadata=cc.metadata,
            )
            self.session.add(child_orm)

        # Commit parent + child chunks
        await self.session.commit()


async def get_ingestion_pipeline(session: AsyncSession) -> IngestionPipeline:
    """Dependency injection for IngestionPipeline."""
    return IngestionPipeline(session)
