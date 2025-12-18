"""Cross-encoder reranking for improving retrieval precision."""
import logging
from typing import List, Optional
import numpy as np

from app.models.document import Document

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import CrossEncoder
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning(
        "sentence-transformers not available. Reranking will use fallback method. "
        "Install with: pip install sentence-transformers"
    )


class CrossEncoderReranker:
    """Rerank retrieved documents using cross-encoder model."""
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"):
        """
        Initialize cross-encoder reranker.
        
        Args:
            model_name: Name of the cross-encoder model to use
                       Default is a lightweight model for fast reranking
        """
        self.model_name = model_name
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the cross-encoder model."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("CrossEncoderReranker: sentence-transformers not available, using fallback")
            return
        
        try:
            logger.info(f"CrossEncoderReranker: Loading model {self.model_name}...")
            self.model = CrossEncoder(self.model_name)
            logger.info("CrossEncoderReranker: Model loaded successfully")
        except Exception as e:
            logger.error(f"CrossEncoderReranker: Error loading model: {e}", exc_info=True)
            self.model = None
    
    async def rerank(
        self,
        query: str,
        documents: List[Document],
        top_k: int = 10
    ) -> List[Document]:
        """
        Rerank documents by relevance to query using cross-encoder.
        
        Args:
            query: Search query
            documents: List of Document objects to rerank
            top_k: Number of top results to return
        
        Returns:
            List of Document objects reranked by relevance score
        """
        if not documents:
            logger.warning("CrossEncoderReranker: No documents to rerank")
            return []
        
        # If model not available, use fallback (return top_k by original similarity)
        if self.model is None:
            logger.warning("CrossEncoderReranker: Using fallback reranking (by similarity)")
            sorted_docs = sorted(
                documents,
                key=lambda d: getattr(d, 'similarity', 0.0),
                reverse=True
            )
            return sorted_docs[:top_k]
        
        logger.info(f"CrossEncoderReranker: Reranking {len(documents)} documents for query: {query[:50]}...")
        
        try:
            # Prepare pairs: (query, document_content)
            pairs = [(query, doc.content) for doc in documents]
            
            # Get relevance scores from cross-encoder
            # This returns a list of scores (one per pair)
            scores = self.model.predict(pairs)
            
            # Add scores to documents
            for doc, score in zip(documents, scores):
                # Store rerank score (normalize similarity to match original format)
                doc.rerank_score = float(score)
                # Update similarity to rerank score for consistency
                doc.similarity = float(score)
            
            # Sort by rerank score (descending)
            reranked_docs = sorted(documents, key=lambda d: d.rerank_score, reverse=True)
            
            logger.info(f"CrossEncoderReranker: Reranked to {len(reranked_docs[:top_k])} top documents")
            return reranked_docs[:top_k]
            
        except Exception as e:
            logger.error(f"CrossEncoderReranker: Error during reranking: {e}", exc_info=True)
            # Fallback: return top_k by original similarity
            sorted_docs = sorted(
                documents,
                key=lambda d: getattr(d, 'similarity', 0.0),
                reverse=True
            )
            return sorted_docs[:top_k]

