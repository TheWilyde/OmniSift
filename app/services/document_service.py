"""Document ingestion service for coordinating file storage, database tracking, and parser triggering."""

import hashlib
import logging
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.services.storage import storage_service

if TYPE_CHECKING:
    from app.services.ingestion_pipeline import IngestionPipeline

logger = logging.getLogger(__name__)


class DocumentIngestionService:
    """Service for handling document upload, storage, and initial database tracking."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def compute_file_hash(self, content: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()

    async def check_duplicate(self, file_hash: str) -> Optional[Document]:
        """Check if a document with the same hash already exists."""
        result = await self.session.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def upload_to_storage(
        self, file_hash: str, content: bytes, content_type: str, original_filename: str
    ) -> str:
        """Upload file to SeaweedFS S3 bucket and return the S3 key."""
        # Generate S3 key using hash-based partitioning
        s3_key = f"{file_hash[:2]}/{file_hash[2:4]}/{file_hash}"

        upload_success = await storage_service.upload_bytes(
            bucket_name=settings.s3_bucket_documents,
            key=s3_key,
            data=content,
            content_type=content_type,
            metadata={
                "original_filename": original_filename,
                "file_hash": file_hash,
            },
        )

        if not upload_success:
            raise RuntimeError("Failed to upload file to object storage")

        return s3_key

    async def create_document_record(
        self,
        title: str,
        source_type: str,
        file_path: str,
        file_hash: str,
        file_size_bytes: int,
        content_type: str,
        allowed_roles: list[str],
        doc_metadata: dict,
    ) -> Document:
        """Create and persist a new document record with 'processing' status."""
        document = Document(
            title=title,
            source_type=source_type,
            file_path=file_path,
            file_hash=file_hash,
            file_size_bytes=file_size_bytes,
            content_type=content_type,
            allowed_roles=allowed_roles,
            doc_metadata=doc_metadata,
            status="processing",
        )

        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)

        logger.info(f"Created document record: {document.id} (hash: {file_hash[:16]}...)")
        return document

    async def ingest_document(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        title: str,
        allowed_roles: list[str],
        doc_metadata: dict,
    ) -> Document:
        """
        Complete document ingestion flow:
        1. Compute file hash
        2. Check for duplicates
        3. Upload to object storage
        4. Create database record with 'processing' status
        """
        # Step 1: Compute hash
        file_hash = await self.compute_file_hash(file_content)

        # Step 2: Check for duplicate
        existing_doc = await self.check_duplicate(file_hash)
        if existing_doc:
            logger.info(f"Duplicate document detected: {existing_doc.id}")
            return existing_doc

        # Step 3: Determine source type from content type
        source_type = self._determine_source_type(content_type, filename)

        # Step 4: Upload to SeaweedFS
        s3_key = await self.upload_to_storage(
            file_hash=file_hash,
            content=file_content,
            content_type=content_type,
            original_filename=filename,
        )

        # Step 5: Create document record
        document = await self.create_document_record(
            title=title,
            source_type=source_type,
            file_path=s3_key,
            file_hash=file_hash,
            file_size_bytes=len(file_content),
            content_type=content_type,
            allowed_roles=allowed_roles,
            doc_metadata=doc_metadata,
        )

        return document

    def _determine_source_type(self, content_type: str, filename: str) -> str:
        """Determine source_type from content type and filename."""
        if content_type == "application/pdf":
            return "pdf"
        elif content_type in ("text/markdown", "text/x-markdown"):
            return "markdown"
        elif content_type == "text/plain":
            # Check file extension for markdown
            if filename.lower().endswith((".md", ".markdown")):
                return "markdown"
            return "text"
        elif "notion" in content_type.lower():
            return "notion"
        else:
            # Default fallback based on extension
            if filename.lower().endswith(".pdf"):
                return "pdf"
            elif filename.lower().endswith((".md", ".markdown")):
                return "markdown"
            return "text"

    async def process_document_pipeline(self, document_id: UUID) -> Document:
        """
        Trigger the full ingestion pipeline for a document.

        This downloads the file from storage and runs:
        parse → chunk → embed → persist (transactional)

        Should be called after ingest_document() creates the initial record.
        """
        # Import here to avoid circular import
        from app.services.ingestion_pipeline import IngestionPipeline

        # Fetch the document
        result = await self.session.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise ValueError(f"Document {document_id} not found")

        if document.status not in ("uploaded", "processing", "failed"):
            logger.warning(f"Document {document_id} already processed (status: {document.status})")
            return document

        # Download file from storage
        file_bytes = await storage_service.download_file(
            bucket_name=settings.s3_bucket_documents,
            key=document.file_path,
        )

        if file_bytes is None:
            raise RuntimeError(f"Failed to download file from storage: {document.file_path}")

        # Run full pipeline
        pipeline = IngestionPipeline(self.session)
        return await pipeline.process_document(
            document_id=document.id,
            file_bytes=file_bytes,
            filename=document.title,
            source_type=document.source_type,
            allowed_roles=document.allowed_roles,
        )


async def get_document_service(session: AsyncSession) -> DocumentIngestionService:
    """Dependency injection for DocumentIngestionService."""
    return DocumentIngestionService(session)