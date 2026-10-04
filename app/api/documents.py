"""Document API routes."""

import json
import uuid
from typing import Annotated, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.config import settings
from app.models.document import Document, ParentChunk, ChildChunk
from app.schemas.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentChunkCreate,
    DocumentChunkResponse,
    DocumentWithChunks,
    DocumentSearchRequest,
    DocumentSearchResult,
)
from app.services.storage import storage_service
from app.services.document_service import get_document_service, DocumentIngestionService

router = APIRouter(prefix="/documents", tags=["documents"])

# Wrapper to avoid FastAPI's dependency analysis issues
async def get_doc_ingestion_service(
    session: AsyncSession = Depends(get_async_session),
) -> DocumentIngestionService:
    return DocumentIngestionService(session)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    response: Response,
    file: UploadFile = File(...),
    title: str = Form(...),
    allowed_roles: str = Form(default='["general"]'),
    metadata: str = Form(default="{}"),
    session: AsyncSession = Depends(get_async_session),
    document_service: DocumentIngestionService = Depends(get_doc_ingestion_service),
) -> DocumentResponse:
    """Upload a document to object storage and create metadata record with processing status.
    
    Triggers background ingestion pipeline: parse → chunk → embed → persist.
    """
    # Validate file type
    if file.content_type not in settings.allowed_file_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not allowed. Allowed types: {settings.allowed_file_types}",
        )

    # Parse form fields
    try:
        allowed_roles_list = json.loads(allowed_roles)
        if not isinstance(allowed_roles_list, list):
            raise ValueError("allowed_roles must be a JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid allowed_roles format: {e}",
        )

    try:
        metadata_dict = json.loads(metadata)
        if not isinstance(metadata_dict, dict):
            raise ValueError("metadata must be a JSON object")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metadata format: {e}",
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.max_file_size_mb}MB",
        )

    # Validate file has content
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file not allowed",
        )

    # Use document service for ingestion (creates record with status="processing")
    try:
        file_hash = await document_service.compute_file_hash(content)
        existing_document = await document_service.check_duplicate(file_hash)
        is_duplicate = existing_document is not None
        document = await document_service.ingest_document(
            file_content=content,
            filename=file.filename or "unknown",
            content_type=file.content_type,
            title=title,
            allowed_roles=allowed_roles_list,
            doc_metadata=metadata_dict,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Return a clear deduplication signal and do not run the pipeline twice.
    if is_duplicate:
        response.status_code = status.HTTP_200_OK
    else:
        background_tasks.add_task(document_service.process_document_pipeline, document.id)

    result = DocumentResponse.model_validate(document)
    result.duplicate = is_duplicate
    return result


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    session: AsyncSession = Depends(get_async_session),
) -> DocumentListResponse:
    """List documents with pagination, including chunk counts."""
    query = select(Document)

    if status_filter:
        query = query.where(Document.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0

    # Apply pagination
    query = query.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    documents = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size

    # Convert documents to response models with chunk counts
    items = []
    for doc in documents:
        # Count parent chunks
        parent_count_result = await session.execute(
            select(func.count(ParentChunk.id)).where(ParentChunk.document_id == doc.id)
        )
        parent_chunk_count = parent_count_result.scalar() or 0

        # Count child chunks
        child_count_result = await session.execute(
            select(func.count(ChildChunk.id)).where(ChildChunk.document_id == doc.id)
        )
        child_chunk_count = child_count_result.scalar() or 0

        doc_data = {
            "id": doc.id,
            "title": doc.title,
            "source_type": doc.source_type,
            "file_path": doc.file_path,
            "file_hash": doc.file_hash,
            "file_size_bytes": doc.file_size_bytes,
            "content_type": doc.content_type,
            "allowed_roles": doc.allowed_roles,
            "doc_metadata": doc.doc_metadata,
            "status": doc.status,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
            "processed_at": doc.processed_at,
            "parent_chunk_count": parent_chunk_count,
            "child_chunk_count": child_chunk_count,
        }
        items.append(DocumentListItem.model_validate(doc_data))
    
    return DocumentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> DocumentResponse:
    """Get a document by ID."""
    result = await session.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/with-chunks", response_model=DocumentWithChunks)
async def get_document_with_chunks(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> DocumentWithChunks:
    """Get a document with its parent and child chunks."""
    result = await session.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Get parent chunks
    parent_chunks_result = await session.execute(
        select(ParentChunk)
        .where(ParentChunk.document_id == document_id)
        .order_by(ParentChunk.chunk_index)
    )
    parent_chunks = parent_chunks_result.scalars().all()

    # Get child chunks
    child_chunks_result = await session.execute(
        select(ChildChunk)
        .where(ChildChunk.document_id == document_id)
        .order_by(ChildChunk.chunk_index)
    )
    child_chunks = child_chunks_result.scalars().all()

    # Use model_validate for document
    doc_response = DocumentResponse.model_validate(document)
    
    # Convert chunks using model_validate
    chunk_list = []
    for chunk in parent_chunks:
        chunk_list.append(DocumentChunkResponse.model_validate(chunk))
    for chunk in child_chunks:
        chunk_list.append(DocumentChunkResponse.model_validate(chunk))

    return DocumentWithChunks(
        **doc_response.model_dump(),
        chunks=chunk_list,
    )


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: uuid.UUID,
    document_update: DocumentUpdate,
    session: AsyncSession = Depends(get_async_session),
) -> DocumentResponse:
    """Update a document."""
    result = await session.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    update_data = document_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(document, field, value)

    await session.commit()
    await session.refresh(document)

    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Delete a document and its file from object storage.
    
    PostgreSQL cascade deletion automatically removes all associated
    parent_chunks and child_chunks due to foreign key constraints.
    """
    result = await session.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Verify chunk counts before deletion (for cascade verification)
    parent_count_before = await session.scalar(
        select(func.count(ParentChunk.id)).where(ParentChunk.document_id == document_id)
    ) or 0
    child_count_before = await session.scalar(
        select(func.count(ChildChunk.id)).where(ChildChunk.document_id == document_id)
    ) or 0

    # Delete from object storage
    await storage_service.delete_file(settings.s3_bucket_documents, document.file_path)

    # Delete from database (cascades to parent_chunks and child_chunks)
    await session.delete(document)
    await session.commit()

    # Verify cascade deletion worked
    parent_count_after = await session.scalar(
        select(func.count(ParentChunk.id)).where(ParentChunk.document_id == document_id)
    ) or 0
    child_count_after = await session.scalar(
        select(func.count(ChildChunk.id)).where(ChildChunk.document_id == document_id)
    ) or 0

    if parent_count_after > 0 or child_count_after > 0:
        # This should never happen with proper cascade config
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Cascade deletion verification failed for document {document_id}: "
            f"parent_chunks before={parent_count_before}, after={parent_count_after}; "
            f"child_chunks before={child_count_before}, after={child_count_after}"
        )


@router.post("/{document_id}/parent-chunks", response_model=List[DocumentChunkResponse])
async def create_parent_chunks(
    document_id: uuid.UUID,
    chunks: List[DocumentChunkCreate],
    session: AsyncSession = Depends(get_async_session),
) -> List[DocumentChunkResponse]:
    """Create parent chunks for a document."""
    # Verify document exists
    result = await session.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Create parent chunks
    created_chunks = []
    for chunk_data in chunks:
        chunk = ParentChunk(
            document_id=document_id,
            chunk_index=chunk_data.chunk_index,
            content=chunk_data.content,
            token_count=chunk_data.token_count,
            page_start=0,  # Will be updated by processing pipeline
            page_end=0,
            heading_hierarchy=[],
            chunk_metadata=chunk_data.metadata,
        )
        session.add(chunk)
        created_chunks.append(chunk)

    await session.commit()

    response_chunks = []
    for chunk in created_chunks:
        await session.refresh(chunk)
        response_chunks.append(DocumentChunkResponse.model_validate(chunk))

    return response_chunks


@router.post("/search", response_model=List[DocumentSearchResult])
async def search_documents(
    search_request: DocumentSearchRequest,
    session: AsyncSession = Depends(get_async_session),
) -> List[DocumentSearchResult]:
    """Search documents using vector similarity."""
    # This is a placeholder for vector search implementation
    # Will be implemented with pgvector in the next phase
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Vector search not yet implemented",
    )
