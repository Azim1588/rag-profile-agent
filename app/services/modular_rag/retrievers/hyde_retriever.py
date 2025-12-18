"""HyDE (Hypothetical Document Embeddings) retriever."""
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_openai import ChatOpenAI

from app.models.document import Document
from app.services.modular_rag.retrievers.dense_retriever import DenseRetriever
from app.core.config import settings

logger = logging.getLogger(__name__)


class HyDERetriever:
    """
    Hypothetical Document Embeddings (HyDE) retriever.
    
    Generates a hypothetical answer to the query using LLM, then uses that
    hypothetical document for dense retrieval. This often improves retrieval
    quality for complex queries.
    """
    
    def __init__(self, dense_retriever: Optional[DenseRetriever] = None):
        """
        Initialize HyDE retriever.
        
        Args:
            dense_retriever: Dense retriever instance for final retrieval
        """
        self.dense_retriever = dense_retriever or DenseRetriever()
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,  # Lower temperature for more consistent hypothetical docs
            max_tokens=300
        )
    
    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 10,
        threshold: float = 0.15,
        metadata_filters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> List[Document]:
        """
        Retrieve documents using HyDE approach.
        
        Process:
        1. Generate hypothetical answer/document for the query
        2. Use hypothetical document for dense retrieval
        3. Return retrieved documents
        
        Args:
            session: Database session
            query: Search query
            top_k: Number of results to return
            threshold: Similarity threshold
            metadata_filters: Optional metadata filters
            use_cache: Whether to use cache
        
        Returns:
            List of Document objects
        """
        logger.info(f"HyDERetriever: Generating hypothetical document for query: {query[:50]}...")
        
        # Step 1: Generate hypothetical answer/document
        hypothetical_doc = await self._generate_hypothetical_answer(query)
        
        if not hypothetical_doc:
            logger.warning("HyDERetriever: Failed to generate hypothetical document, falling back to direct retrieval")
            # Fallback to direct dense retrieval
            return await self.dense_retriever.retrieve(
                session=session,
                query=query,
                top_k=top_k,
                threshold=threshold,
                metadata_filters=metadata_filters,
                use_cache=use_cache
            )
        
        logger.info(f"HyDERetriever: Generated hypothetical document ({len(hypothetical_doc)} chars)")
        
        # Step 2: Use hypothetical document for dense retrieval
        # The hypothetical document should contain relevant terms and context,
        # which will match better with actual documents in the vector store
        results = await self.dense_retriever.retrieve(
            session=session,
            query=hypothetical_doc,  # Use hypothetical doc instead of original query
            top_k=top_k,
            threshold=threshold,
            metadata_filters=metadata_filters,
            use_cache=False  # Don't cache hypothetical queries
        )
        
        logger.info(f"HyDERetriever: Retrieved {len(results)} documents using hypothetical document")
        return results
    
    async def _generate_hypothetical_answer(self, query: str) -> str:
        """
        Generate a hypothetical answer/document that would answer the query.
        
        This hypothetical document should:
        - Contain relevant terms and concepts
        - Be written in a style similar to the actual documents
        - Answer the query as if it were in the knowledge base
        
        Args:
            query: User query
        
        Returns:
            Hypothetical answer/document string
        """
        system_prompt = """You are generating a hypothetical document that would answer a user's query.

Generate a brief, factual answer (2-4 sentences) that would appear in a professional profile/resume document.

Guidelines:
- Write in third person (as if describing someone)
- Use concrete terms, technologies, and facts
- Focus on professional experience, skills, projects, education
- Be specific but concise
- Match the style of a resume or professional profile

Do NOT:
- Use phrases like "based on", "according to", "it appears"
- Make up specific details (dates, company names, etc.)
- Write in first person
- Add meta-commentary

Just write the answer as if it were a factual statement from a professional profile."""
        
        prompt = f"""Query: {query}

Generate a hypothetical professional profile excerpt that would answer this query:"""
        
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            
            hypothetical = response.content.strip()
            return hypothetical
            
        except Exception as e:
            logger.error(f"HyDERetriever: Error generating hypothetical answer: {e}", exc_info=True)
            return ""

