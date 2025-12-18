"""Hybrid retrieval combining dense and sparse methods."""
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.services.modular_rag.retrievers.dense_retriever import DenseRetriever
from app.services.modular_rag.retrievers.sparse_retriever import SparseRetriever
from app.services.modular_rag.retrievers.fusion import ReciprocalRankFusion

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid retrieval using both dense and sparse methods with RRF fusion."""
    
    def __init__(
        self,
        dense_retriever: Optional[DenseRetriever] = None,
        sparse_retriever: Optional[SparseRetriever] = None,
        rrf_k: int = 60
    ):
        """
        Initialize hybrid retriever.
        
        Args:
            dense_retriever: Dense retriever instance
            sparse_retriever: Sparse retriever instance
            rrf_k: RRF constant for fusion
        """
        self.dense_retriever = dense_retriever or DenseRetriever()
        self.sparse_retriever = sparse_retriever or SparseRetriever()
        self.fusion = ReciprocalRankFusion(k=rrf_k)
    
    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 20,
        dense_top_k: int = 20,
        sparse_top_k: int = 20,
        threshold: float = 0.15,
        metadata_filters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> List[Document]:
        """
        Retrieve documents using hybrid dense + sparse retrieval with RRF fusion.
        
        Args:
            session: Database session
            query: Search query
            top_k: Final number of results to return after fusion
            dense_top_k: Number of results from dense retrieval
            sparse_top_k: Number of results from sparse retrieval
            threshold: Similarity threshold for dense retrieval
            metadata_filters: Optional metadata filters
            use_cache: Whether to use cached embeddings for dense retrieval
        
        Returns:
            List of Document objects sorted by fused RRF score
        """
        logger.info(f"HybridRetriever: Starting hybrid retrieval for query: {query[:50]}...")
        
        # Run dense and sparse retrieval in parallel (if possible)
        # For now, run sequentially but structure for async parallel execution
        dense_results = await self.dense_retriever.retrieve(
            session=session,
            query=query,
            top_k=dense_top_k,
            threshold=threshold,
            metadata_filters=metadata_filters,
            use_cache=use_cache
        )
        
        sparse_results = await self.sparse_retriever.retrieve(
            session=session,
            query=query,
            top_k=sparse_top_k,
            metadata_filters=metadata_filters
        )
        
        # Combine using RRF
        result_sets = [dense_results, sparse_results]
        fused_results = self.fusion.fuse(result_sets, top_k=top_k)
        
        logger.info(
            f"HybridRetriever: Fused {len(dense_results)} dense + "
            f"{len(sparse_results)} sparse → {len(fused_results)} results"
        )
        
        return fused_results

