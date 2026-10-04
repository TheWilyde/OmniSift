#!/usr/bin/env python
"""
Test data seeding script for OmniSift.
Creates sample documents with different roles for testing RBAC and search.
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.models.document import Document, ParentChunk, ChildChunk
from app.services.embedding_service import create_embedding_provider
from app.chunking import ChunkingEngine, ParentChunkData, ChildChunkData
from app.parsers import parser_factory, ParsedDocument, ParsedElement
from app.parsers.markdown_parser import MarkdownParser


# Test document contents
FINANCE_DOC_CONTENT = """
# Q3 2024 Financial Report

## Executive Summary
The third quarter of 2024 showed strong revenue growth of 15% year-over-year,
driven primarily by the enterprise segment. Net income reached $42.3M, exceeding
analyst expectations by $3.2M.

## Revenue Recognition
Under ASC 606, revenue is recognized when control of goods or services transfers
to the customer. For subscription contracts, revenue is recognized ratably over
the contract term. Implementation fees are recognized upon completion of
onboarding milestones.

Key metrics:
- ARR: $180M (up 22% YoY)
- NRR: 118% (best in class)
- Gross margin: 78%

## Account ACC-2024-0042
Major enterprise account signed in July 2024. Contract value: $2.4M over 3 years.
Revenue recognition schedule: $200K per quarter starting Q3 2024.

## Incident Response Protocol
For personally identifiable data (PII) breaches, the following protocol applies:
1. Immediate containment within 4 hours of detection
2. Legal notification within 24 hours per GDPR Article 33
3. Customer communication within 72 hours
4. Full forensic report within 30 days

The privacy team handles all client data incidents through the secure portal.
"""

GENERAL_DOC_CONTENT = """
# Company Policy Handbook

## Section 4.2: Remote Work Policy
Effective January 2024, all employees may work remotely up to 3 days per week.
Team leads must approve schedules in advance. Core hours are 10am-3pm EST.

## Data Classification
Public: Marketing materials, press releases
Internal: Org charts, meeting notes
Confidential: Customer lists, financial projections
Restricted: PII, credentials, encryption keys

## Security Awareness
Annual training required for all staff. Phishing simulations conducted quarterly.
Report suspicious emails to security@company.com.

## Expense Reimbursement
Submit within 30 days with receipts. Per diem rates: $75/day domestic, $120/day international.
"""

HR_DOC_CONTENT = """
# Employee Benefits Guide 2024

## Health Insurance
Three tiers available: Bronze, Silver, Gold. Company covers 80% of premiums.
Open enrollment: November 1-15 annually.

## 401(k) Matching
100% match on first 4% of salary. Vesting immediate.
Roth and traditional options available.

## Parental Leave
12 weeks paid at 100% for primary caregivers.
4 weeks paid at 100% for secondary caregivers.
Additional 4 weeks unpaid available.
"""


async def create_test_documents(session: AsyncSession):
    """Create test documents with different roles."""
    
    embedding_provider = create_embedding_provider()
    chunking_engine = ChunkingEngine(
        parent_min_tokens=800,
        parent_max_tokens=1200,
        child_min_tokens=200,
        child_max_tokens=300,
        child_overlap_tokens=30,
    )
    
    documents_data = [
        {
            "title": "Q3 2024 Financial Report",
            "content": FINANCE_DOC_CONTENT,
            "allowed_roles": ["finance", "admin"],
            "source_type": "markdown",
            "filename": "q3_financial_report.md",
        },
        {
            "title": "Company Policy Handbook",
            "content": GENERAL_DOC_CONTENT,
            "allowed_roles": ["general", "hr", "finance", "admin"],
            "source_type": "markdown",
            "filename": "policy_handbook.md",
        },
        {
            "title": "Employee Benefits Guide 2024",
            "content": HR_DOC_CONTENT,
            "allowed_roles": ["hr", "admin"],
            "source_type": "markdown",
            "filename": "benefits_guide.md",
        },
    ]
    
    created_docs = []
    
    for doc_data in documents_data:
        # Check if already exists
        file_hash = hashlib.sha256(doc_data["content"].encode()).hexdigest()
        result = await session.execute(
            text("SELECT id FROM documents WHERE file_hash = :hash"),
            {"hash": file_hash}
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"Document '{doc_data['title']}' already exists (ID: {existing})")
            created_docs.append(existing)
            continue
        
        # Create document record
        doc_id = uuid.uuid4()
        s3_key = f"{file_hash[:2]}/{file_hash[2:4]}/{file_hash}"
        
        document = Document(
            id=doc_id,
            title=doc_data["title"],
            source_type=doc_data["source_type"],
            file_path=s3_key,
            file_hash=file_hash,
            file_size_bytes=len(doc_data["content"].encode()),
            content_type="text/markdown",
            allowed_roles=doc_data["allowed_roles"],
            doc_metadata={},
            status="completed",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
        )
        session.add(document)
        await session.flush()
        
        # Parse and chunk using the markdown parser directly
        parser = MarkdownParser()
        parsed = await parser.parse(doc_data["content"].encode(), doc_data["filename"])
        
        parent_chunks, child_chunks = chunking_engine.chunk_document(
            parsed, doc_data["allowed_roles"]
        )
        
        # Generate embeddings for child chunks
        child_texts = [c.content for c in child_chunks]
        embeddings = await embedding_provider.embed_texts(child_texts)
        
        for child, embedding in zip(child_chunks, embeddings):
            child.embedding = embedding
        
        # Persist parent chunks
        parent_orm_objects = []
        for pc in parent_chunks:
            parent_orm = ParentChunk(
                document_id=doc_id,
                chunk_index=pc.chunk_index,
                content=pc.content,
                token_count=pc.token_count,
                page_start=pc.page_start,
                page_end=pc.page_end,
                heading_hierarchy=pc.heading_hierarchy,
                chunk_metadata=pc.metadata,
            )
            session.add(parent_orm)
            parent_orm_objects.append(parent_orm)
        
        await session.flush()
        
        # Map parent chunk_index to parent ID
        parent_id_map = {p.chunk_index: p.id for p in parent_orm_objects}
        
        # Persist child chunks
        for cc in child_chunks:
            parent_idx = cc.metadata.get("parent_chunk_index", 0)
            parent_id = parent_id_map.get(parent_idx)
            
            child_orm = ChildChunk(
                parent_id=parent_id,
                document_id=doc_id,
                chunk_index=cc.chunk_index,
                content=cc.content,
                token_count=cc.token_count,
                page_number=cc.page_number,
                char_start=cc.char_start,
                char_end=cc.char_end,
                bbox=cc.bbox,
                allowed_roles=cc.allowed_roles,
                embedding=cc.embedding,
                chunk_metadata=cc.metadata,
            )
            session.add(child_orm)
        
        await session.commit()
        created_docs.append(doc_id)
        print(f"Created document: {doc_data['title']} (ID: {doc_id})")
        print(f"  - Parent chunks: {len(parent_chunks)}")
        print(f"  - Child chunks: {len(child_chunks)}")
    
    return created_docs


async def main():
    """Main entry point."""
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print("Seeding test data...")
        await create_test_documents(session)
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())