"""Dense retrieval using pgvector embeddings."""
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.document import Document
from app.services.vector_store import VectorStoreService

logger = logging.getLogger(__name__)


class DenseRetriever:
    """Dense retrieval using vector embeddings and pgvector."""
    
    def __init__(self, vector_store: Optional[VectorStoreService] = None):
        self.vector_store = vector_store or VectorStoreService()
    
    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 20,
        threshold: float = 0.15,
        metadata_filters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> List[Document]:
        """
        Retrieve documents using dense vector similarity search.
        
        Args:
            session: Database session
            query: Search query
            top_k: Number of results to return
            threshold: Minimum similarity threshold
            metadata_filters: Optional metadata filters
            use_cache: Whether to use cached embeddings
        
        Returns:
            List of Document objects with similarity scores
        """
        logger.info(f"DenseRetriever: Retrieving top {top_k} documents for query: {query[:50]}...")
        
        results = await self.vector_store.similarity_search(
            session=session,
            query=query,
            top_k=top_k,
            threshold=threshold,
            metadata_filters=metadata_filters,
            use_cache=use_cache
        )
        
        logger.info(f"DenseRetriever: Found {len(results)} documents")
        return results

