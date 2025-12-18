"""Multi-hop iterative retrieval for complex queries."""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_openai import ChatOpenAI

from app.models.document import Document
from app.services.modular_rag.retriever_pool import RetrieverPool
from app.services.modular_rag.reranker import CrossEncoderReranker
from app.services.modular_rag.task_adapter import TaskAdapter
from app.core.config import settings

logger = logging.getLogger(__name__)


class MultiHopRetriever:
    """Iterative retrieval for complex multi-hop queries."""
    
    def __init__(
        self,
        retriever_pool: Optional[RetrieverPool] = None,
        reranker: Optional[CrossEncoderReranker] = None
    ):
        """
        Initialize multi-hop retriever.
        
        Args:
            retriever_pool: Retriever pool instance
            reranker: Reranker instance (optional)
        """
        self.retriever_pool = retriever_pool or RetrieverPool()
        self.reranker = reranker
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=200
        )
    
    async def retrieve_iterative(
        self,
        session: AsyncSession,
        initial_query: str,
        max_hops: int = 3,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
        strategy: str = "hybrid"
    ) -> List[Document]:
        """
        Perform iterative retrieval for complex queries.
        
        Process:
        1. Retrieve documents for initial query
        2. Generate follow-up query based on initial results
        3. Retrieve for follow-up query
        4. Combine and deduplicate
        5. Rerank all collected documents
        
        Args:
            session: Database session
            initial_query: Original user query
            max_hops: Maximum number of retrieval iterations
            conversation_context: Conversation history (for query generation)
            strategy: Retrieval strategy to use
        
        Returns:
            List of Document objects (deduplicated and reranked)
        """
        logger.info(f"MultiHopRetriever: Starting iterative retrieval for query: {initial_query[:50]}...")
        
        all_docs = []
        seen_hashes = set()
        current_query = initial_query
        
        for hop in range(max_hops):
            logger.info(f"MultiHopRetriever: Hop {hop + 1}/{max_hops} - Query: {current_query[:50]}...")
            
            # Retrieve documents for current query
            try:
                docs = await self.retriever_pool.retrieve(
                    session=session,
                    strategy=strategy,
                    query=current_query,
                    top_k=10,  # Get more docs per hop for better coverage
                    threshold=settings.SIMILARITY_THRESHOLD,
                    use_cache=True
                )
            except Exception as e:
                logger.error(f"MultiHopRetriever: Error in hop {hop + 1}: {e}", exc_info=True)
                break
            
            # Deduplicate within this hop
            for doc in docs:
                doc_hash = getattr(doc, 'content_hash', None) or str(getattr(doc, 'id', hash(doc.content)))
                if doc_hash not in seen_hashes:
                    seen_hashes.add(doc_hash)
                    all_docs.append(doc)
            
            logger.info(f"MultiHopRetriever: Hop {hop + 1} found {len(docs)} docs, total unique: {len(all_docs)}")
            
            # Generate follow-up query if not last hop
            if hop < max_hops - 1 and all_docs:
                try:
                    next_query = await self._generate_followup_query(
                        initial_query=initial_query,
                        current_query=current_query,
                        retrieved_docs=all_docs,
                        conversation_context=conversation_context
                    )
                    
                    if next_query and next_query.strip() != current_query.strip():
                        current_query = next_query
                        logger.info(f"MultiHopRetriever: Generated follow-up query: {current_query[:50]}...")
                    else:
                        # No useful follow-up query generated, stop iteration
                        logger.info("MultiHopRetriever: No useful follow-up query, stopping iteration")
                        break
                except Exception as e:
                    logger.error(f"MultiHopRetriever: Error generating follow-up query: {e}", exc_info=True)
                    break
        
        # Rerank all collected documents
        if self.reranker and all_docs:
            logger.info(f"MultiHopRetriever: Reranking {len(all_docs)} collected documents...")
            all_docs = await self.reranker.rerank(
                query=initial_query,
                documents=all_docs,
                top_k=min(10, len(all_docs))  # Return top 10 from all hops
            )
            logger.info(f"MultiHopRetriever: After reranking: {len(all_docs)} documents")
        
        logger.info(f"MultiHopRetriever: Completed {hop + 1} hops, returning {len(all_docs)} documents")
        return all_docs
    
    async def _generate_followup_query(
        self,
        initial_query: str,
        current_query: str,
        retrieved_docs: List[Document],
        conversation_context: Optional[List[Dict[str, Any]]]
    ) -> str:
        """
        Generate follow-up query based on initial query and retrieved documents.
        
        Uses LLM to analyze what information is still missing and generate
        a refined query to retrieve complementary information.
        
        Args:
            initial_query: Original user query
            current_query: Query used in current hop
            retrieved_docs: Documents retrieved so far
            conversation_context: Conversation history
        
        Returns:
            Follow-up query string
        """
        # Extract key content from retrieved docs (limit to avoid token limits)
        doc_summaries = []
        for doc in retrieved_docs[:5]:  # Use top 5 for context
            content = doc.content[:200] if hasattr(doc, 'content') else str(doc)[:200]
            doc_summaries.append(f"- {content}...")
        
        docs_context = "\n".join(doc_summaries)
        
        # Build prompt for LLM
        system_prompt = """You are a query refinement assistant for multi-hop retrieval.

Your job is to analyze the original query and the documents retrieved so far, then generate a refined follow-up query that will help retrieve complementary or missing information.

Guidelines:
- Focus on aspects of the original query that aren't fully answered by current documents
- Generate a specific, focused query (not too broad)
- If the current documents fully answer the query, respond with "COMPLETE" (don't generate a new query)
- Keep queries concise (1-2 sentences max)

Return only the refined query, or "COMPLETE" if no further retrieval is needed."""
        
        prompt = f"""Original query: {initial_query}

Current query used: {current_query}

Documents retrieved so far:
{docs_context}

Generate a refined follow-up query to retrieve complementary information, or respond "COMPLETE" if enough information has been gathered:"""
        
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            
            followup_query = response.content.strip()
            
            # Check if LLM indicates retrieval is complete
            if followup_query.upper() in ["COMPLETE", "DONE", "SUFFICIENT", "ENOUGH"]:
                return ""
            
            return followup_query
            
        except Exception as e:
            logger.error(f"MultiHopRetriever: Error generating follow-up query: {e}", exc_info=True)
            return ""

