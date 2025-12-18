"""Pluggable retriever pool for different retrieval strategies."""
import logging
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.modular_rag.retrievers.dense_retriever import DenseRetriever
from app.services.modular_rag.retrievers.sparse_retriever import SparseRetriever
from app.services.modular_rag.retrievers.hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)


class RetrieverPool:
    """Pool of retrievers for different strategies."""
    
    def __init__(
        self,
        dense_retriever: Optional[DenseRetriever] = None,
        sparse_retriever: Optional[SparseRetriever] = None,
        hybrid_retriever: Optional[HybridRetriever] = None
    ):
        """
        Initialize retriever pool.
        
        Args:
            dense_retriever: Dense retriever instance
            sparse_retriever: Sparse retriever instance
            hybrid_retriever: Hybrid retriever instance
        """
        self.dense_retriever = dense_retriever or DenseRetriever()
        self.sparse_retriever = sparse_retriever or SparseRetriever()
        self.hybrid_retriever = hybrid_retriever or HybridRetriever(
            dense_retriever=self.dense_retriever,
            sparse_retriever=self.sparse_retriever
        )
        
        # Strategy mapping
        self.retrievers: Dict[str, any] = {
            "dense": self.dense_retriever,
            "sparse": self.sparse_retriever,
            "hybrid": self.hybrid_retriever
        }
    
    async def retrieve(
        self,
        session: AsyncSession,
        strategy: str,
        query: str,
        top_k: int = 20,
        threshold: float = 0.15,
        metadata_filters: Optional[Dict] = None,
        use_cache: bool = True,
        **kwargs
    ):
        """
        Retrieve documents using specified strategy.
        
        Args:
            session: Database session
            strategy: Retrieval strategy ('dense', 'sparse', 'hybrid')
            query: Search query
            top_k: Number of results to return
            threshold: Similarity threshold (for dense/hybrid)
            metadata_filters: Optional metadata filters
            use_cache: Whether to use cache (for dense/hybrid)
            **kwargs: Additional strategy-specific parameters
        
        Returns:
            List of Document objects
        """
        retriever = self.retrievers.get(strategy)
        if not retriever:
            logger.warning(f"RetrieverPool: Unknown strategy '{strategy}', using 'hybrid'")
            retriever = self.hybrid_retriever
        
        logger.info(f"RetrieverPool: Using strategy '{strategy}' for query: {query[:50]}...")
        
        # Call appropriate retriever
        if strategy == "dense":
            return await retriever.retrieve(
                session=session,
                query=query,
                top_k=top_k,
                threshold=threshold,
                metadata_filters=metadata_filters,
                use_cache=use_cache
            )
        elif strategy == "sparse":
            return await retriever.retrieve(
                session=session,
                query=query,
                top_k=top_k,
                metadata_filters=metadata_filters
            )
        else:  # hybrid
            return await retriever.retrieve(
                session=session,
                query=query,
                top_k=top_k,
                threshold=threshold,
                metadata_filters=metadata_filters,
                use_cache=use_cache,
                **kwargs
            )

