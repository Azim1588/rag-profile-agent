"""Sparse retrieval using PostgreSQL full-text search (BM25-like)."""
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from app.models.document import Document

logger = logging.getLogger(__name__)


class SparseRetriever:
    """Sparse retrieval using PostgreSQL full-text search."""
    
    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 20,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Retrieve documents using PostgreSQL full-text search.
        
        Uses ts_rank for ranking (similar to BM25).
        
        Args:
            session: Database session
            query: Search query (will be converted to tsquery)
            top_k: Number of results to return
            metadata_filters: Optional metadata filters
        
        Returns:
            List of Document objects with similarity scores (ts_rank)
        """
        logger.info(f"SparseRetriever: Retrieving top {top_k} documents for query: {query[:50]}...")
        
        # Convert query to tsquery format
        # Handle multiple words by joining with & (AND) operator
        query_terms = query.split()
        tsquery = " & ".join([term.strip() for term in query_terms if term.strip()])
        
        # Build SQL query with full-text search
        base_sql = """
            SELECT 
                id, filename, content_hash, content, metadata, embedding, 
                source, created_at, updated_at,
                ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) as similarity
            FROM documents
            WHERE to_tsvector('english', content) @@ plainto_tsquery('english', :query)
              AND embedding IS NOT NULL
        """
        
        params = {
            "query": query,
            "top_k": top_k
        }
        
        # Add metadata filtering if provided
        if metadata_filters:
            # Use JSONB containment operator (@>)
            for key, value in metadata_filters.items():
                base_sql += f" AND metadata @> :filter_{key}::jsonb"
                params[f"filter_{key}"] = f'{{"{key}": "{value}"}}'
        
        # Order by similarity (ts_rank) and limit
        base_sql += " ORDER BY similarity DESC LIMIT :top_k"
        
        try:
            result = await session.execute(text(base_sql), params)
            rows = result.fetchall()
            
            # Convert rows to Document objects
            documents = []
            for row in rows:
                doc = Document(
                    id=row[0],
                    filename=row[1],
                    content_hash=row[2],
                    content=row[3],
                    meta=row[4] if row[4] else {},
                    embedding=row[5],
                    source=row[6],
                    created_at=row[7],
                    updated_at=row[8]
                )
                # Add similarity score as attribute
                doc.similarity = float(row[9]) if row[9] else 0.0
                documents.append(doc)
            
            logger.info(f"SparseRetriever: Found {len(documents)} documents")
            return documents
            
        except Exception as e:
            logger.error(f"SparseRetriever: Error during retrieval: {e}", exc_info=True)
            return []

