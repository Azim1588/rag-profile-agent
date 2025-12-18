"""
Script to delete ALL documents from the database and vector store.
WARNING: This will permanently delete all documents and embeddings!

Usage:
    # Run in Docker (recommended)
    sudo docker compose exec app python scripts/delete_all_documents.py
    
    # With confirmation prompt (default)
    sudo docker compose exec app python scripts/delete_all_documents.py
    
    # Skip confirmation (use with caution)
    sudo docker compose exec app python scripts/delete_all_documents.py --yes
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import argparse
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.models.document import Document
from app.models.document_source import DocumentSource


async def delete_all_documents(confirm: bool = True, delete_sources: bool = True):
    """
    Delete all documents from the database and optionally document sources.
    
    Args:
        confirm: If True, ask for confirmation before deleting
        delete_sources: If True, also delete document sources
    """
    print("=" * 100)
    print("⚠️  DELETE ALL DOCUMENTS FROM DATABASE")
    print("=" * 100)
    print()
    print("WARNING: This will permanently delete:")
    print("  - All document chunks from the 'documents' table")
    print("  - All vector embeddings")
    if delete_sources:
        print("  - All document sources from 'document_sources' table")
    print()
    
    async with get_async_session() as session:
        # Count documents before deletion
        result = await session.execute(select(func.count(Document.id)))
        doc_count = result.scalar()
        
        result = await session.execute(select(func.count(DocumentSource.id)))
        source_count = result.scalar()
        
        print(f"📊 Current Database State:")
        print(f"  Documents (chunks):     {doc_count}")
        print(f"  Document Sources:       {source_count}")
        print()
        
        if doc_count == 0 and source_count == 0:
            print("✅ Database is already empty. Nothing to delete.")
            return
        
        # Confirmation
        if confirm:
            print("⚠️  Are you sure you want to delete ALL documents?")
            print("   This action cannot be undone!")
            response = input("   Type 'DELETE ALL' to confirm: ")
            
            if response != "DELETE ALL":
                print("❌ Deletion cancelled. Documents remain unchanged.")
                return
        
        print()
        print("🗑️  Starting deletion...")
        print()
        
        # Delete all documents (chunks with embeddings)
        if doc_count > 0:
            print(f"Deleting {doc_count} document chunks...")
            await session.execute(delete(Document))
            deleted_docs = doc_count
            print(f"✅ Deleted {deleted_docs} document chunks")
        else:
            deleted_docs = 0
            print("ℹ️  No documents to delete")
        
        # Delete all document sources (optional)
        if delete_sources and source_count > 0:
            print(f"Deleting {source_count} document sources...")
            await session.execute(delete(DocumentSource))
            deleted_sources = source_count
            print(f"✅ Deleted {deleted_sources} document sources")
        else:
            deleted_sources = 0
            if not delete_sources:
                print("ℹ️  Document sources preserved (use --delete-sources to remove)")
        
        # Commit the deletion
        await session.commit()
        
        print()
        print("=" * 100)
        print("✅ DELETION COMPLETE")
        print("=" * 100)
        print()
        print(f"Deleted:")
        print(f"  - {deleted_docs} document chunks (with embeddings)")
        if delete_sources:
            print(f"  - {deleted_sources} document sources")
        print()
        print("📝 Note: To re-populate documents, sync from S3 bucket:")
        print("   sudo docker compose exec celery celery -A app.tasks.celery_app call app.tasks.document_sync.sync_documents_from_s3")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Delete all documents from the database and vector store"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt (use with caution)"
    )
    parser.add_argument(
        "--keep-sources",
        action="store_true",
        help="Keep document sources, only delete document chunks"
    )
    
    args = parser.parse_args()
    
    confirm = not args.yes
    delete_sources = not args.keep_sources
    
    asyncio.run(delete_all_documents(confirm=confirm, delete_sources=delete_sources))

