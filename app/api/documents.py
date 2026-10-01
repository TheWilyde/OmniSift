"""Document API routes."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.config import settings
from app.models.document import Document, ParentChunk, ChildChunk
from app.schemas.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentListResponse,
    DocumentChunkCreate,
    DocumentChunkResponse,
    DocumentWithChunks,
    DocumentSearchRequest,
    DocumentSearchResult,
)
from app.services.storage import storage_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
) -> DocumentResponse:
    """Upload a document to object storage and create metadata record."""
    # Validate file type
    if file.content_type not in settings.allowed_file_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not allowed. Allowed types: {settings.allowed_file_types}",
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.max_file_size_mb}MB",
        )

    # Generate file hash (SHA-256)
    import hashlib
    file_hash = hashlib.sha256(content).hexdigest()
    
    # Check for duplicate
    existing = await session.execute(select(Document).where(Document.file_hash == file_hash))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document with this content already exists",
        )

    # Generate S3 key (file_path)
    s3_key = f"{file_hash[:2]}/{file_hash[2:4]}/{file_hash}"

    # Upload to object storage
    upload_success = await storage_service.upload_bytes(
        bucket_name=settings.s3_bucket_documents,
        key=s3_key,
        data=content,
        content_type=file.content_type,
        metadata={
            "original_filename": file.filename or "unknown",
            "file_hash": file_hash,
        },
    )

    if not upload_success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to object storage",
        )

    # Create document record
    document = Document(
        title=file.filename or "unknown",
        source_type="pdf" if file.content_type == "application/pdf" else "markdown" if file.content_type == "text/markdown" else "text",
        file_path=s3_key,
        file_hash=file_hash,
        file_size_bytes=len(content),
        content_type=file.content_type,
        allowed_roles=["general"],  # Default role
        doc_metadata={},
        status="uploaded",
    )

    session.add(document)
    await session.commit()
    await session.refresh(document)

    return DocumentResponse.model_validate(document)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    session: AsyncSession = Depends(get_async_session),
) -> DocumentListResponse:
    """List documents with pagination."""
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

    # Convert documents to response models
    items = []
    for doc in documents:
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
        }
        items.append(DocumentResponse.model_validate(doc_data))
    
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
    """Delete a document and its file from object storage."""
    result = await session.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Delete from object storage
    await storage_service.delete_file(settings.s3_bucket_documents, document.file_path)

    # Delete from database (cascades to parent_chunks and child_chunks)
    await session.delete(document)
    await session.commit()


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