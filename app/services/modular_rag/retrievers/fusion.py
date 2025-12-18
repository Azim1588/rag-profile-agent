"""Reciprocal Rank Fusion (RRF) for combining multiple retrieval results."""
import logging
from typing import List, Dict
from collections import defaultdict

from app.models.document import Document

logger = logging.getLogger(__name__)


class ReciprocalRankFusion:
    """Combine multiple retrieval result sets using Reciprocal Rank Fusion."""
    
    def __init__(self, k: int = 60):
        """
        Initialize RRF with parameter k.
        
        Args:
            k: RRF constant (typically 60). Lower k gives more weight to top results.
        """
        self.k = k
    
    def fuse(
        self, 
        result_sets: List[List[Document]], 
        top_k: int = 20
    ) -> List[Document]:
        """
        Fuse multiple result sets using Reciprocal Rank Fusion.
        
        RRF formula: score(d) = Σ(1 / (k + rank(d, R_i)))
        
        Args:
            result_sets: List of result sets, each containing Document objects
            top_k: Number of top results to return
        
        Returns:
            List of Document objects sorted by fused score (descending)
        """
        if not result_sets or not any(result_sets):
            logger.warning("RRF: No result sets provided, returning empty list")
            return []
        
        # Dictionary to store fused scores: {document_id: {doc, score}}
        fused_scores: Dict[str, Dict] = defaultdict(lambda: {"doc": None, "score": 0.0, "seen_in": []})
        
        # Process each result set
        for result_set_idx, result_set in enumerate(result_sets):
            if not result_set:
                continue
            
            # Calculate RRF score for each document in this result set
            for rank, doc in enumerate(result_set, start=1):
                # Use content_hash as unique identifier (more reliable than id)
                doc_id = doc.content_hash if hasattr(doc, 'content_hash') else str(doc.id)
                
                # RRF score: 1 / (k + rank)
                rrf_score = 1.0 / (self.k + rank)
                
                # Add to fused score
                fused_scores[doc_id]["score"] += rrf_score
                fused_scores[doc_id]["doc"] = doc
                fused_scores[doc_id]["seen_in"].append(result_set_idx)
        
        # Sort by fused score (descending)
        sorted_results = sorted(
            fused_scores.values(),
            key=lambda x: x["score"],
            reverse=True
        )
        
        # Extract documents and add fused score
        fused_documents = []
        for item in sorted_results[:top_k]:
            doc = item["doc"]
            # Store fused score as similarity
            doc.similarity = item["score"]
            # Add metadata about which retrievers found this doc
            if not hasattr(doc, 'meta') or doc.meta is None:
                doc.meta = {}
            doc.meta['rrf_score'] = item["score"]
            doc.meta['retrievers'] = item["seen_in"]
            fused_documents.append(doc)
        
        logger.info(f"RRF: Fused {len(result_sets)} result sets into {len(fused_documents)} documents")
        return fused_documents

