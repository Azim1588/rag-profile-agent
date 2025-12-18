import hashlib
import boto3
from typing import List
import asyncio
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.services.vector_store import VectorStoreService
from app.services.document_processor import DocumentProcessor
from app.core.database import get_async_session
from app.models.document_source import DocumentSource
from app.models.document import Document
from sqlalchemy import select, and_, delete


def get_s3_client():
    """Get or create S3 client with current settings."""
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION
    )


@celery_app.task(name="app.tasks.document_sync.sync_documents_from_s3")
def sync_documents_from_s3():
    """Scheduled task to sync documents from S3"""
    try:
        # Always create a fresh event loop for Celery tasks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_async_sync_documents())
        finally:
            loop.close()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to sync documents in Celery task: {e}", exc_info=True)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def _download_file_with_retry(bucket: str, key: str):
    """Download file from S3 with retry logic"""
    from typing import Tuple
    # Returns Tuple[bytes, dict]
    s3_client = get_s3_client()
    file_obj = s3_client.get_object(Bucket=bucket, Key=key)
    file_bytes = file_obj['Body'].read()
    metadata = {
        'etag': file_obj.get('ETag', '').strip('"'),
        'last_modified': file_obj.get('LastModified'),
        'content_length': file_obj.get('ContentLength', 0)
    }
    return file_bytes, metadata


async def _async_sync_documents():
    """Async implementation of document sync with incremental ingestion"""
    vector_store = VectorStoreService()
    doc_processor = DocumentProcessor()
    
    # List objects in S3 bucket
    s3_client = get_s3_client()
    try:
        response = s3_client.list_objects_v2(Bucket=settings.S3_BUCKET)
    except Exception as e:
        print(f"Error listing S3 bucket: {e}")
        return
    
    if 'Contents' not in response:
        print("No documents found in S3 bucket")
        return
    
    async with get_async_session() as session:
        for obj in response['Contents']:
            key = obj['Key']
            
            # Skip directories (S3 keys ending with /)
            if key.endswith('/'):
                continue
            
            try:
                # Get S3 object metadata
                s3_etag = obj.get('ETag', '').strip('"')
                s3_last_modified = obj.get('LastModified')
                s3_size = obj.get('Size', 0)
                
                # Check if we've processed this file before
                result = await session.execute(
                    select(DocumentSource).where(DocumentSource.s3_key == key)
                )
                existing_source = result.scalar_one_or_none()
                
                # Determine if file needs processing
                needs_processing = False
                if not existing_source:
                    needs_processing = True
                    print(f"New file detected: {key}")
                elif (existing_source.etag != s3_etag or 
                      existing_source.last_modified != s3_last_modified or
                      existing_source.status == 'failed'):
                    needs_processing = True
                    print(f"File changed or failed previously: {key}")
                    # Update status to processing
                    existing_source.status = 'processing'
                    existing_source.updated_at = datetime.utcnow()
                else:
                    print(f"File {key} already synced and unchanged, skipping")
                    continue
                
                # Create or update DocumentSource record
                if not existing_source:
                    existing_source = DocumentSource(
                        s3_key=key,
                        status='processing'
                    )
                    session.add(existing_source)
                else:
                    existing_source.status = 'processing'
                    existing_source.updated_at = datetime.utcnow()
                
                await session.commit()
                
                # Download file with retry
                try:
                    file_bytes, file_metadata = await _download_file_with_retry(
                        settings.S3_BUCKET, key
                    )
                except Exception as e:
                    existing_source.status = 'failed'
                    existing_source.error_message = str(e)
                    existing_source.updated_at = datetime.utcnow()
                    await session.commit()
                    print(f"Failed to download {key} after retries: {e}")
                    continue
                
                # Calculate file hash
                file_hash = hashlib.sha256(file_bytes).hexdigest()
                
                # Process document to get chunks
                chunks = await doc_processor.process_document(key, file_bytes)
                
                if not chunks:
                    existing_source.status = 'failed'
                    existing_source.error_message = "No chunks extracted"
                    existing_source.updated_at = datetime.utcnow()
                    await session.commit()
                    print(f"No chunks extracted from {key}, skipping")
                    continue
                
                # Check if any chunks from this file already exist
                # (If filename matches and we've processed it before, we might skip)
                result = await session.execute(
                    select(Document).where(Document.filename == key).limit(1)
                )
                existing_doc = result.scalar_one_or_none()
                
                # Remove old chunks if file was updated
                if existing_doc and needs_processing:
                    await session.execute(
                        delete(Document).where(Document.filename == key)
                    )
                    await session.commit()
                    print(f"Removed old chunks for updated file: {key}")
                
                # Add each chunk to vector store
                chunks_added = 0
                embedding_errors = []
                for chunk in chunks:
                    try:
                        await vector_store.add_document(
                            session=session,
                            filename=chunk["filename"],
                            content=chunk["content"],
                            metadata=chunk["metadata"]
                        )
                        chunks_added += 1
                    except Exception as e:
                        error_msg = f"Error adding chunk {chunk.get('metadata', {}).get('chunk_index', 'unknown')}: {str(e)}"
                        print(error_msg)
                        embedding_errors.append(error_msg)
                        continue
                
                # Only mark as synced if at least one chunk was successfully embedded
                if chunks_added == 0:
                    # All chunks failed - mark as failed
                    existing_source.status = 'failed'
                    existing_source.error_message = f"Failed to embed all chunks. Errors: {'; '.join(embedding_errors[:3])}"
                    existing_source.updated_at = datetime.utcnow()
                    await session.commit()
                    print(f"❌ Failed to sync document: {key} (all {len(chunks)} chunks failed embedding)")
                else:
                    # At least some chunks succeeded - mark as synced
                    existing_source.status = 'synced'
                    existing_source.etag = s3_etag
                    existing_source.last_modified = s3_last_modified
                    existing_source.file_hash = file_hash
                    existing_source.file_size = s3_size
                    existing_source.synced_at = datetime.utcnow()
                    existing_source.error_message = None
                    existing_source.updated_at = datetime.utcnow()
                    
                    await session.commit()
                    
                    if len(embedding_errors) > 0:
                        print(f"⚠️  Partially synced document: {key} ({chunks_added}/{len(chunks)} chunks added, {len(embedding_errors)} failed)")
                    else:
                        print(f"✅ Synced document: {key} ({chunks_added} chunks added)")
                
            except Exception as e:
                print(f"Error processing document {key}: {e}")
                # Update DocumentSource with error
                try:
                    result = await session.execute(
                        select(DocumentSource).where(DocumentSource.s3_key == key)
                    )
                    source = result.scalar_one_or_none()
                    if source:
                        source.status = 'failed'
                        source.error_message = str(e)
                        source.updated_at = datetime.utcnow()
                        await session.commit()
                except:
                    pass
                continue
