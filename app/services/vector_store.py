import hashlib
import logging
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, and_
from langchain_openai import OpenAIEmbeddings
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.document import Document
from app.core.config import settings
from app.services.cache import cache_service

logger = logging.getLogger(__name__)


class VectorStoreService:
    def __init__(self):
        # Store embedding model version for tracking
        self.embedding_model_version = settings.OPENAI_EMBEDDING_MODEL
        self.embeddings = OpenAIEmbeddings(
            model=self.embedding_model_version,
            openai_api_key=settings.OPENAI_API_KEY
        )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _generate_embedding_with_retry(self, text: str) -> List[float]:
        """Generate embedding with retry logic and caching"""
        # Check cache first
        cached_embedding = await cache_service.get_embedding(text)
        if cached_embedding:
            logger.debug(f"Cache hit for embedding: {text[:50]}...")
            return cached_embedding
        
        # Generate embedding
        try:
            embedding = await self.embeddings.aembed_query(text)
            # Cache the result
            await cache_service.set_embedding(text, embedding)
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding (retrying): {e}")
            raise
    
    async def add_document(
        self,
        session: AsyncSession,
        filename: str,
        content: str,
        metadata: dict = None
    ) -> Document:
        """Add document with embedding to vector store"""
        # Calculate content hash for deduplication
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Check if document already exists
        result = await session.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        existing_doc = result.scalar_one_or_none()
        
        if existing_doc:
            return existing_doc
        
        # Generate embedding with retry
        try:
            embedding = await self._generate_embedding_with_retry(content)
        except Exception as e:
            print(f"Failed to generate embedding after retries: {e}")
            raise
        
        # Enhance metadata with embedding model version
        enhanced_metadata = metadata.copy() if metadata else {}
        enhanced_metadata['embedding_model'] = self.embedding_model_version
        enhanced_metadata['embedding_dimension'] = len(embedding)
        
        # Create document
        document = Document(
            filename=filename,
            content_hash=content_hash,
            content=content,
            meta=enhanced_metadata,
            embedding=embedding
        )
        
        session.add(document)
        await session.commit()
        await session.refresh(document)
        
        return document
    
    async def similarity_search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 5,
        threshold: float = 0.7,
        metadata_filters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> List[Document]:
        """Search for similar documents using cosine similarity with optional metadata filtering"""
        # Check cache for retrieval results (only if no metadata filters, as they change results)
        if use_cache and not metadata_filters:
            cached_results = await cache_service.get_retrieval_results(query)
            if cached_results:
                logger.debug(f"Cache hit for retrieval: {query[:50]}...")
                # Convert cached dicts back to Document objects
                documents = []
                for doc_dict in cached_results:
                    doc = Document(
                        id=doc_dict.get('id'),
                        filename=doc_dict.get('filename'),
                        content=doc_dict.get('content'),
                        content_hash=doc_dict.get('content_hash'),
                        meta=doc_dict.get('metadata', {}),
                        source=doc_dict.get('source')
                    )
                    if 'similarity' in doc_dict:
                        doc.similarity = doc_dict['similarity']
                    documents.append(doc)
                return documents
        
        # Generate query embedding with retry
        try:
            query_embedding = await self._generate_embedding_with_retry(query)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return []
        
        # Convert embedding list to string format for pgvector
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        
        # Build SQL query with optional metadata filtering
        base_sql = """
            SELECT id, filename, content_hash, content, metadata, embedding, 
                   source, created_at, updated_at,
                   1 - (embedding <=> CAST(:query_embedding AS vector)) AS similarity
            FROM documents
            WHERE embedding IS NOT NULL
              AND 1 - (embedding <=> CAST(:query_embedding AS vector)) > :threshold
        """
        
        # Add metadata filtering if provided
        params = {
            "query_embedding": embedding_str,
            "threshold": threshold,
            "top_k": top_k
        }
        
        if metadata_filters:
            # Use JSONB containment operator (@>) for filtering
            # This allows filtering by any key-value pairs in the metadata JSONB column
            import json
            base_sql += " AND metadata @> :metadata_filter::jsonb"
            params["metadata_filter"] = json.dumps(metadata_filters)
        
        base_sql += """
            ORDER BY embedding <=> CAST(:query_embedding AS vector)
            LIMIT :top_k
        """
        
        query_sql = text(base_sql)
        
        try:
            result = await session.execute(query_sql, params)
            
            # Map results to Document objects
            rows = result.mappings().fetchall()
            logger.info(f"Vector search query: '{query}' returned {len(rows)} documents (threshold={threshold})")
        except Exception as e:
            logger.error(f"Error executing vector search: {e}", exc_info=True)
            return []
        
        documents = []
        for row in rows:
            doc = Document(
                id=row['id'],
                filename=row['filename'],
                content_hash=row['content_hash'],
                content=row['content'],
                meta=row['metadata'],
                embedding=row['embedding'],
                source=row['source'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            # Attach similarity score as attribute (not stored in DB)
            doc.similarity = float(row['similarity']) if row['similarity'] else None
            documents.append(doc)
        
        # Cache retrieval results (only if no metadata filters)
        if use_cache and not metadata_filters and documents:
            # Convert Document objects to dicts for caching
            cache_data = [
                {
                    'id': str(doc.id),
                    'filename': doc.filename,
                    'content': doc.content,
                    'content_hash': doc.content_hash,
                    'metadata': doc.meta if hasattr(doc, 'meta') else {},
                    'source': doc.source,
                    'similarity': getattr(doc, 'similarity', None)
                }
                for doc in documents
            ]
            await cache_service.set_retrieval_results(query, cache_data)
        
        return documents
    
    async def update_document(
        self,
        session: AsyncSession,
        content_hash: str,
        new_content: str,
        metadata: dict = None
    ) -> Optional[Document]:
        """Update existing document (for incremental sync)"""
        result = await session.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        document = result.scalar_one_or_none()
        
        if not document:
            return None
        
        # Generate new embedding with retry
        try:
            new_embedding = await self._generate_embedding_with_retry(new_content)
        except Exception as e:
            print(f"Failed to generate embedding for update: {e}")
            raise
        
        # Update document
        document.content = new_content
        document.embedding = new_embedding
        if metadata:
            document.meta = metadata
        
        # Update embedding model version in metadata
        if document.meta:
            document.meta['embedding_model'] = self.embedding_model_version
            document.meta['embedding_dimension'] = len(new_embedding)
        
        await session.commit()
        await session.refresh(document)
        
        return document
