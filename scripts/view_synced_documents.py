"""
Script to view synced documents from S3 bucket.
Shows DocumentSource status and Document chunks count.
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.core.database import get_async_session
from app.models.document_source import DocumentSource
from app.models.document import Document


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    if size_bytes is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def format_datetime(dt: datetime) -> str:
    """Format datetime for display"""
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


async def view_synced_documents():
    """View all synced documents with status and chunk counts"""
    print("=" * 100)
    print("SYNCED DOCUMENTS VIEWER")
    print("=" * 100)
    print()

    async with get_async_session() as session:
        # Get all document sources with their chunk counts
        query = select(
            DocumentSource.s3_key,
            DocumentSource.status,
            DocumentSource.file_size,
            DocumentSource.synced_at,
            DocumentSource.error_message,
            DocumentSource.last_modified,
            func.count(Document.id).label('chunk_count')
        ).outerjoin(
            Document, Document.filename == DocumentSource.s3_key
        ).group_by(
            DocumentSource.id,
            DocumentSource.s3_key,
            DocumentSource.status,
            DocumentSource.file_size,
            DocumentSource.synced_at,
            DocumentSource.error_message,
            DocumentSource.last_modified
        ).order_by(
            DocumentSource.synced_at.desc().nullslast(),
            DocumentSource.created_at.desc()
        )
        
        result = await session.execute(query)
        rows = result.all()
        
        if not rows:
            print("❌ No documents found in DocumentSource table.")
            print("   Documents may not have been synced yet.")
            return
        
        # Summary statistics
        total_files = len(rows)
        synced_count = sum(1 for row in rows if row.status == 'synced')
        pending_count = sum(1 for row in rows if row.status == 'pending')
        failed_count = sum(1 for row in rows if row.status == 'failed')
        processing_count = sum(1 for row in rows if row.status == 'processing')
        total_chunks = sum(row.chunk_count for row in rows)
        
        print("📊 SUMMARY")
        print("-" * 100)
        print(f"Total Files:          {total_files}")
        print(f"  ✅ Synced:          {synced_count}")
        print(f"  ⏳ Pending:         {pending_count}")
        print(f"  🔄 Processing:      {processing_count}")
        print(f"  ❌ Failed:          {failed_count}")
        print(f"Total Chunks:         {total_chunks}")
        print(f"Avg Chunks/File:      {total_chunks / synced_count if synced_count > 0 else 0:.1f}")
        print()
        
        # Group by status
        print("=" * 100)
        print("DETAILED VIEW")
        print("=" * 100)
        print()
        
        # Show synced documents first
        synced_rows = [row for row in rows if row.status == 'synced']
        if synced_rows:
            print(f"✅ SYNCED DOCUMENTS ({len(synced_rows)})")
            print("-" * 100)
            print(f"{'Filename':<50} {'Size':<12} {'Chunks':<8} {'Synced At':<20}")
            print("-" * 100)
            for row in synced_rows:
                filename = row.s3_key.split('/')[-1] if '/' in row.s3_key else row.s3_key
                size_str = format_size(row.file_size)
                synced_str = format_datetime(row.synced_at)
                print(f"{filename:<50} {size_str:<12} {row.chunk_count:<8} {synced_str:<20}")
            print()
        
        # Show failed documents
        failed_rows = [row for row in rows if row.status == 'failed']
        if failed_rows:
            print(f"❌ FAILED DOCUMENTS ({len(failed_rows)})")
            print("-" * 100)
            print(f"{'Filename':<50} {'Size':<12} {'Error':<30}")
            print("-" * 100)
            for row in failed_rows:
                filename = row.s3_key.split('/')[-1] if '/' in row.s3_key else row.s3_key
                size_str = format_size(row.file_size)
                error = (row.error_message or "Unknown error")[:30]
                print(f"{filename:<50} {size_str:<12} {error:<30}")
            print()
        
        # Show pending documents
        pending_rows = [row for row in rows if row.status == 'pending']
        if pending_rows:
            print(f"⏳ PENDING DOCUMENTS ({len(pending_rows)})")
            print("-" * 100)
            print(f"{'Filename':<50} {'Size':<12} {'Created At':<20}")
            print("-" * 100)
            for row in pending_rows:
                filename = row.s3_key.split('/')[-1] if '/' in row.s3_key else row.s3_key
                size_str = format_size(row.file_size)
                # Get created_at separately
                source_query = select(DocumentSource).where(DocumentSource.s3_key == row.s3_key)
                source_result = await session.execute(source_query)
                source = source_result.scalar_one()
                created_str = format_datetime(source.created_at)
                print(f"{filename:<50} {size_str:<12} {created_str:<20}")
            print()
        
        # Show processing documents
        processing_rows = [row for row in rows if row.status == 'processing']
        if processing_rows:
            print(f"🔄 PROCESSING DOCUMENTS ({len(processing_rows)})")
            print("-" * 100)
            print(f"{'Filename':<50} {'Size':<12}")
            print("-" * 100)
            for row in processing_rows:
                filename = row.s3_key.split('/')[-1] if '/' in row.s3_key else row.s3_key
                size_str = format_size(row.file_size)
                print(f"{filename:<50} {size_str:<12}")
            print()
        
        # Detailed view for a specific file (optional)
        print("=" * 100)
        print("📄 DETAILED INFORMATION")
        print("=" * 100)
        print()
        
        # Show first 10 synced documents with full details
        print("Top 10 Synced Documents (Full Details):")
        print("-" * 100)
        
        for i, row in enumerate(synced_rows[:10], 1):
            filename = row.s3_key.split('/')[-1] if '/' in row.s3_key else row.s3_key
            print(f"\n{i}. {filename}")
            print(f"   S3 Key:        {row.s3_key}")
            print(f"   Status:        {row.status}")
            print(f"   File Size:     {format_size(row.file_size)}")
            print(f"   Chunks:        {row.chunk_count}")
            print(f"   Synced At:     {format_datetime(row.synced_at)}")
            print(f"   Last Modified: {format_datetime(row.last_modified)}")
            
            # Get sample chunks
            if row.chunk_count > 0:
                chunks_query = select(Document).where(
                    Document.filename == row.s3_key
                ).limit(3)
                chunks_result = await session.execute(chunks_query)
                chunks = chunks_result.scalars().all()
                
                print(f"   Sample Chunks:")
                for j, chunk in enumerate(chunks, 1):
                    content_preview = chunk.content[:80].replace('\n', ' ')
                    print(f"      {j}. {content_preview}...")
        
        if len(synced_rows) > 10:
            print(f"\n   ... and {len(synced_rows) - 10} more documents")
        
        print()
        print("=" * 100)
        print("✅ View complete!")
        print("=" * 100)


if __name__ == "__main__":
    asyncio.run(view_synced_documents())

