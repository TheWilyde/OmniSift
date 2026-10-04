#!/usr/bin/env python
"""
Demo data seeding script for OmniSift.

Creates a reproducible sample data setup with 4 curated documents across
different departments (finance, legal, hr, general) so anyone can see
the system working immediately with RBAC boundaries.

Usage:
    python scripts/seed_demo_data.py
    python scripts/seed_demo_data.py --wipe  # Clean slate
"""

import asyncio
import hashlib
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.models.document import Document, ParentChunk, ChildChunk
from app.services.embedding_service import create_embedding_provider
from app.chunking import ChunkingEngine
from app.parsers import parser_factory
from app.parsers.base import ParsedDocument


# Sample document configurations
SAMPLE_DOCS: List[Dict[str, Any]] = [
    {
        "filename": "q3_2024_financial_report.md",
        "title": "Q3 2024 Financial Report",
        "source_type": "markdown",
        "allowed_roles": ["finance", "admin"],
        "department": "finance",
    },
    {
        "filename": "vendor_master_services_agreement.md",
        "title": "Vendor Master Services Agreement",
        "source_type": "markdown",
        "allowed_roles": ["legal", "admin"],
        "department": "legal",
    },
    {
        "filename": "employee_handbook_2024.md",
        "title": "Employee Handbook 2024",
        "source_type": "markdown",
        "allowed_roles": ["hr", "admin"],
        "department": "hr",
    },
    {
        "filename": "company_all_hands_q3.md",
        "title": "Company All-Hands Q3 2024",
        "source_type": "markdown",
        "allowed_roles": ["general", "finance", "legal", "hr", "admin"],
        "department": "general",
    },
]


async def wipe_demo_data(session: AsyncSession) -> None:
    """Remove all existing demo data from database and storage."""
    print("Wiping existing demo data...")
    
    # Get file hashes of sample docs to identify them
    sample_hashes = []
    for doc_config in SAMPLE_DOCS:
        file_path = Path(__file__).parent.parent / "data" / "sample_docs" / doc_config["filename"]
        if file_path.exists():
            content = file_path.read_bytes()
            file_hash = hashlib.sha256(content).hexdigest()
            sample_hashes.append(file_hash)
    
    if sample_hashes:
        # Delete child chunks first (FK constraint)
        placeholders = ",".join([f":hash_{i}" for i in range(len(sample_hashes))])
        params = {f"hash_{i}": h for i, h in enumerate(sample_hashes)}
        
        # Delete child chunks via document_id
        await session.execute(text(f"""
            DELETE FROM child_chunks 
            WHERE document_id IN (
                SELECT id FROM documents WHERE file_hash IN ({placeholders})
            )
        """), params)
        
        # Delete parent chunks
        await session.execute(text(f"""
            DELETE FROM parent_chunks 
            WHERE document_id IN (
                SELECT id FROM documents WHERE file_hash IN ({placeholders})
            )
        """), params)
        
        # Delete documents
        await session.execute(text(f"""
            DELETE FROM documents WHERE file_hash IN ({placeholders})
        """), params)
        
        await session.commit()
        print(f"  Deleted {len(sample_hashes)} demo documents and their chunks")


async def process_document(
    session: AsyncSession,
    doc_config: Dict[str, Any],
    embedding_provider,
    chunking_engine: ChunkingEngine,
) -> Dict[str, Any]:
    """Process a single sample document: parse, chunk, embed, persist."""
    
    file_path = Path(__file__).parent.parent / "data" / "sample_docs" / doc_config["filename"]
    
    if not file_path.exists():
        print(f"  WARNING: File not found: {file_path}")
        return {"status": "missing", "filename": doc_config["filename"]}
    
    # Read file content
    content = file_path.read_bytes()
    file_hash = hashlib.sha256(content).hexdigest()
    file_size = len(content)
    
    # Check if already exists
    result = await session.execute(
        text("SELECT id FROM documents WHERE file_hash = :hash"),
        {"hash": file_hash}
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        print(f"  SKIP: {doc_config['title']} already exists (ID: {existing})")
        return {"status": "exists", "id": str(existing), "title": doc_config["title"]}
    
    print(f"  Processing: {doc_config['title']}...")
    
    # Create document record
    doc_id = uuid.uuid4()
    s3_key = f"demo/{file_hash[:2]}/{file_hash[2:4]}/{file_hash}"
    
    document = Document(
        id=doc_id,
        title=doc_config["title"],
        source_type=doc_config["source_type"],
        file_path=s3_key,
        file_hash=file_hash,
        file_size_bytes=file_size,
        content_type="text/markdown",
        allowed_roles=doc_config["allowed_roles"],
        doc_metadata={"department": doc_config["department"], "demo": True},
        status="completed",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc),
    )
    session.add(document)
    await session.flush()
    
    # Parse document
    parser = parser_factory.get_parser(doc_config["source_type"])
    parsed: ParsedDocument = await parser.parse(content, doc_config["filename"])
    
    # Chunk document
    parent_chunks, child_chunks = chunking_engine.chunk_document(
        parsed, doc_config["allowed_roles"]
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
    
    result = {
        "status": "created",
        "id": str(doc_id),
        "title": doc_config["title"],
        "department": doc_config["department"],
        "allowed_roles": doc_config["allowed_roles"],
        "parent_chunks": len(parent_chunks),
        "child_chunks": len(child_chunks),
        "file_size_kb": round(file_size / 1024, 1),
    }
    
    print(f"    [OK] Created: {doc_config['title']}")
    print(f"      ID: {doc_id}")
    print(f"      Parent chunks: {len(parent_chunks)}")
    print(f"      Child chunks: {len(child_chunks)}")
    print(f"      Roles: {doc_config['allowed_roles']}")
    
    return result


async def main(wipe: bool = False) -> None:
    """Main entry point."""
    print("=" * 60)
    print("OMNISIFT DEMO DATA SEEDING")
    print("=" * 60)
    
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        if wipe:
            await wipe_demo_data(session)
        
        # Initialize services
        embedding_provider = create_embedding_provider()
        chunking_engine = ChunkingEngine(
            parent_min_tokens=800,
            parent_max_tokens=1200,
            child_min_tokens=200,
            child_max_tokens=300,
            child_overlap_tokens=30,
        )
        
        print(f"\nProcessing {len(SAMPLE_DOCS)} sample documents...\n")
        
        results = []
        for doc_config in SAMPLE_DOCS:
            result = await process_document(
                session, doc_config, embedding_provider, chunking_engine
            )
            results.append(result)
        
        # Print summary table
        print("\n" + "=" * 60)
        print("SEEDING SUMMARY")
        print("=" * 60)
        print(f"{'Document':<40} {'Dept':<8} {'Parents':>7} {'Children':>8} {'Roles':<25}")
        print("-" * 90)
        
        total_parents = 0
        total_children = 0
        
        for r in results:
            if r["status"] in ("created", "exists"):
                dept = r.get("department", "N/A")
                parents = r.get("parent_chunks", 0)
                children = r.get("child_chunks", 0)
                roles = ",".join(r.get("allowed_roles", []))[:24]
                title = r["title"][:39]
                print(f"{title:<40} {dept:<8} {parents:>7} {children:>8} {roles:<25}")
                total_parents += parents
                total_children += children
            else:
                print(f"{r['filename']:<40} {'MISSING':<8} {'N/A':>7} {'N/A':>8} {'N/A':<25}")
        
        print("-" * 90)
        print(f"{'TOTAL':<40} {'':<8} {total_parents:>7} {total_children:>8}")
        
        print("\n" + "=" * 60)
        print("ROLE-BASED ACCESS MATRIX")
        print("=" * 60)
        print(f"{'Role':<12} {'Finance':<10} {'Legal':<10} {'HR':<10} {'General':<10} {'Admin':<10}")
        print("-" * 60)
        
        roles = ["finance", "legal", "hr", "general", "admin"]
        for role in roles:
            accessible = []
            for r in results:
                if r["status"] in ("created", "exists") and role in r.get("allowed_roles", []):
                    accessible.append(r["title"][:20])
            print(f"{role:<12} {len(accessible):<10} {'':<10} {'':<10} {'':<10} {'':<10}")
            for doc_title in accessible:
                print(f"{'':<12} - {doc_title}")
        
        print("\n[SUCCESS] Demo data seeding complete!")
        print("\nNext steps:")
        print("  1. Start backend:  uv run uvicorn app.main:app --reload")
        print("  2. Start frontend: cd frontend && pnpm dev")
        print("  3. Visit http://localhost:3000")
        print("  4. Try role switcher to test RBAC boundaries")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed OmniSift demo data")
    parser.add_argument("--wipe", action="store_true", help="Wipe existing demo data first")
    args = parser.parse_args()
    
    asyncio.run(main(wipe=args.wipe))