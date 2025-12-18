#!/usr/bin/env python3
"""
Script to delete a document from the database.
Deletes all chunks for a given filename from the documents table.
"""
import asyncio
import sys
import os
sys.path.insert(0, '/app' if os.path.exists('/app/app') else os.getcwd())

from app.core.database import get_async_session
from sqlalchemy import text, delete
from app.models.document import Document
from app.models.document_source import DocumentSource

async def delete_document(filename: str):
    """Delete all document chunks for a given filename."""
    print("=" * 70)
    print("Delete Document from Database")
    print("=" * 70)
    print()
    print(f"Filename: {filename}")
    print()
    
    async with get_async_session() as session:
        # Check how many documents exist with this filename
        result = await session.execute(
            text("SELECT COUNT(*) FROM documents WHERE filename = :filename"),
            {"filename": filename}
        )
        count_before = result.scalar()
        
        if count_before == 0:
            print(f"❌ No documents found with filename: {filename}")
            print()
            # Check if file exists with different case or similar
            result = await session.execute(
                text("SELECT DISTINCT filename FROM documents WHERE filename ILIKE :pattern LIMIT 10"),
                {"pattern": f"%{filename}%"}
            )
            similar_files = result.fetchall()
            if similar_files:
                print("   Similar filenames found:")
                for file in similar_files:
                    print(f"      - {file[0]}")
            return
        
        print(f"📊 Found {count_before} document chunk(s) with filename: {filename}")
        print()
        
        # Show some details
        result = await session.execute(
            text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(embedding) as with_embeddings,
                    MIN(created_at) as first_created,
                    MAX(created_at) as last_created
                FROM documents 
                WHERE filename = :filename
            """),
            {"filename": filename}
        )
        stats = result.fetchone()
        print(f"   Total chunks: {stats[0]}")
        print(f"   With embeddings: {stats[1]}")
        print(f"   First created: {stats[2]}")
        print(f"   Last created: {stats[3]}")
        print()
        
        # Confirm deletion
        print("⚠️  WARNING: This will permanently delete all chunks for this file!")
        print()
        
        # Delete from documents table
        print("🗑️  Deleting document chunks...")
        await session.execute(
            delete(Document).where(Document.filename == filename)
        )
        await session.commit()
        print(f"   ✅ Deleted {count_before} document chunk(s)")
        print()
        
        # Also check and optionally delete from document_sources if it exists
        result = await session.execute(
            text("SELECT COUNT(*) FROM document_sources WHERE s3_key = :key"),
            {"key": filename}
        )
        source_count = result.scalar()
        
        if source_count > 0:
            print(f"📋 Found {source_count} entry(ies) in document_sources table")
            print("   Deleting from document_sources...")
            await session.execute(
                delete(DocumentSource).where(DocumentSource.s3_key == filename)
            )
            await session.commit()
            print("   ✅ Deleted from document_sources")
            print()
        
        # Verify deletion
        result = await session.execute(
            text("SELECT COUNT(*) FROM documents WHERE filename = :filename"),
            {"filename": filename}
        )
        count_after = result.scalar()
        
        if count_after == 0:
            print("✅ Verification: All documents deleted successfully!")
        else:
            print(f"⚠️  Warning: {count_after} document(s) still exist (this shouldn't happen)")
        
        print()
        print("=" * 70)
        print("Deletion complete!")
        print("=" * 70)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "test_resume.txt"
    
    asyncio.run(delete_document(filename))

