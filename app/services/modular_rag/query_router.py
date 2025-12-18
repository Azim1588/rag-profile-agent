"""Query routing and analysis for determining retrieval strategy."""
import logging
from typing import Dict, Any, List, Optional
from enum import Enum
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Query type classification."""
    FACTUAL_QA = "factual_qa"
    CONVERSATIONAL = "conversational"
    MULTI_HOP = "multi_hop"
    SUMMARIZATION = "summarization"
    CLARIFICATION = "clarification"
    GREETING = "greeting"  # Greetings/small talk that don't need retrieval
    OUT_OF_SCOPE = "out_of_scope"  # Questions outside the RAG's purpose


class QueryAnalysis:
    """Query analysis result."""
    
    def __init__(
        self,
        query_type: QueryType,
        requires_rewriting: bool = False,
        requires_expansion: bool = False,
        retrieval_strategy: str = "hybrid",
        metadata_filters: Optional[Dict[str, Any]] = None,
        expanded_queries: Optional[List[str]] = None,
        rewritten_query: Optional[str] = None
    ):
        self.query_type = query_type
        self.requires_rewriting = requires_rewriting
        self.requires_expansion = requires_expansion
        self.retrieval_strategy = retrieval_strategy
        self.metadata_filters = metadata_filters or {}
        self.expanded_queries = expanded_queries or []
        self.rewritten_query = rewritten_query


class QueryRouter:
    """Routes queries to appropriate retrieval strategies."""
    
    def __init__(self):
        """Initialize query router with LLM for classification."""
        # Use lightweight model for fast classification
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,  # Low temperature for consistent classification
            max_tokens=200
        )
    
    async def analyze(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> QueryAnalysis:
        """
        Analyze query and determine routing strategy.
        
        Args:
            query: User query
            conversation_history: Previous conversation messages
        
        Returns:
            QueryAnalysis object with routing information
        """
        logger.info(f"QueryRouter: Analyzing query: {query[:50]}...")
        
        # Simple keyword-based classification (fast, no LLM call)
        # Can be enhanced with LLM-based classification later
        query_lower = query.lower()
        
        # Detect query type
        query_type = self._classify_query_type(query_lower, conversation_history)
        
        # Determine if query needs rewriting (based on length, clarity, history)
        requires_rewriting = self._needs_rewriting(query, conversation_history)
        
        # Determine if query needs expansion (complex, multi-part questions)
        requires_expansion = self._needs_expansion(query_lower)
        
        # Determine retrieval strategy based on query type
        # Skip retrieval for greetings and out-of-scope questions
        if query_type == QueryType.GREETING or query_type == QueryType.OUT_OF_SCOPE:
            retrieval_strategy = "none"  # No retrieval needed
        else:
            retrieval_strategy = self._determine_strategy(query_type)
        
        # Extract metadata filters (simple keyword extraction for now)
        metadata_filters = self._extract_metadata_filters(query_lower)
        
        # Generate expanded queries if needed
        expanded_queries = None
        if requires_expansion:
            expanded_queries = await self._expand_query(query, conversation_history)
        
        # Rewrite query if needed
        rewritten_query = None
        if requires_rewriting:
            rewritten_query = await self._rewrite_query(query, conversation_history)
        
        analysis = QueryAnalysis(
            query_type=query_type,
            requires_rewriting=requires_rewriting,
            requires_expansion=requires_expansion,
            retrieval_strategy=retrieval_strategy,
            metadata_filters=metadata_filters,
            expanded_queries=expanded_queries,
            rewritten_query=rewritten_query
        )
        
        logger.info(
            f"QueryRouter: Query type={query_type.value}, "
            f"strategy={retrieval_strategy}, "
            f"rewriting={requires_rewriting}, "
            f"expansion={requires_expansion}"
        )
        
        return analysis
    
    def _classify_query_type(self, query_lower: str, history: Optional[List]) -> QueryType:
        """Classify query type using simple heuristics."""
        # Greeting/small talk detection (should come first, highest priority)
        greeting_patterns = [
            "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
            "how are you", "how's it going", "what's up", "howdy",
            "thanks", "thank you", "thank", "thanks a lot",
            "nice to meet you", "pleased to meet you",
            "goodbye", "bye", "see you", "have a nice day"
        ]
        # Check if query is ONLY a greeting (no substantive content)
        words = query_lower.split()
        if len(words) <= 4:  # Short messages are likely greetings
            if any(greeting in query_lower for greeting in greeting_patterns):
                return QueryType.GREETING
        
        # Multi-hop indicators
        multi_hop_indicators = ["compare", "difference", "relationship", "how does", "why does"]
        if any(indicator in query_lower for indicator in multi_hop_indicators):
            return QueryType.MULTI_HOP
        
        # Summarization indicators
        summarization_indicators = ["summarize", "summary", "overview", "brief", "list all"]
        if any(indicator in query_lower for indicator in summarization_indicators):
            return QueryType.SUMMARIZATION
        
        # Conversational indicators (references to previous context)
        conversational_indicators = ["also", "what about", "tell me more", "and", "what else"]
        if history and len(history) > 2:
            if any(indicator in query_lower for indicator in conversational_indicators):
                return QueryType.CONVERSATIONAL
        
        # Clarification indicators
        clarification_indicators = ["what do you mean", "clarify", "explain"]
        if any(indicator in query_lower for indicator in clarification_indicators):
            return QueryType.CLARIFICATION
        
        # Out-of-scope detection - questions clearly not about Azim
        # Check for specific out-of-scope indicators first (before general patterns)
        specific_out_of_scope_indicators = [
            "weather", "temperature", "forecast", "rain", "snow", "sunny",
            "what time", "what day", "timezone",
            "news", "current events", "headlines",
            "recipe", "cooking", "how to cook",
            "joke", "jokes", "funny", "humor", "tell me a joke",
            "story", "stories", "anecdote",
        ]
        azim_keywords = ["azim", "your", "khamis"]
        # Note: Removed "he", "him", "you" as they're too short and cause false positives
        # (e.g., "he" matches in "weather", "you" matches in "today")
        # Check if keywords appear as whole words to avoid substring matches
        query_words = set(query_lower.split())
        has_azim_reference = any(keyword in query_words for keyword in azim_keywords) or any(keyword in query_lower for keyword in ["azim", "khamis"])
        has_out_of_scope = any(indicator in query_lower for indicator in specific_out_of_scope_indicators)
        
        # If it has out-of-scope indicators and no Azim reference, it's out of scope
        if has_out_of_scope and not has_azim_reference:
            return QueryType.OUT_OF_SCOPE
        
        # Default: factual Q&A
        return QueryType.FACTUAL_QA
    
    def _needs_rewriting(self, query: str, history: Optional[List]) -> bool:
        """Determine if query needs rewriting for better retrieval."""
        # Short queries might need expansion
        if len(query.split()) < 3:
            return True
        
        # Queries with pronouns might need context
        pronouns = ["he", "she", "it", "they", "this", "that", "these", "those"]
        if any(pronoun in query.lower() for pronoun in pronouns) and history:
            return True
        
        return False
    
    def _needs_expansion(self, query_lower: str) -> bool:
        """Determine if query needs expansion (multiple sub-questions)."""
        # Complex queries with multiple parts
        connectors = ["and", "or", "also", "what about", "how about"]
        if sum(connector in query_lower for connector in connectors) > 1:
            return True
        
        return False
    
    def _determine_strategy(self, query_type: QueryType) -> str:
        """Determine retrieval strategy based on query type."""
        from app.core.config import settings
        
        strategy_map = {
            QueryType.GREETING: "none",  # No retrieval for greetings
            QueryType.OUT_OF_SCOPE: "none",  # No retrieval for out-of-scope questions
            QueryType.FACTUAL_QA: "hyde" if settings.ENABLE_HYDE else "hybrid",
            QueryType.CONVERSATIONAL: "dense",
            QueryType.MULTI_HOP: "multi_hop" if settings.ENABLE_MULTI_HOP else "hybrid",
            QueryType.SUMMARIZATION: "hybrid",
            QueryType.CLARIFICATION: "dense"
        }
        return strategy_map.get(query_type, "hybrid")
    
    def _extract_metadata_filters(self, query_lower: str) -> Dict[str, Any]:
        """Extract metadata filters from query (simple keyword matching)."""
        filters = {}
        
        # Extract technology/skill filters
        tech_keywords = {
            "python": "Python",
            "fastapi": "FastAPI",
            "postgresql": "PostgreSQL",
            "docker": "Docker",
            "react": "React",
            "javascript": "JavaScript"
        }
        
        for keyword, value in tech_keywords.items():
            if keyword in query_lower:
                filters["skills"] = value
                break
        
        return filters
    
    async def _expand_query(self, query: str, history: Optional[List]) -> List[str]:
        """Expand complex query into sub-queries."""
        # For now, simple expansion (can be enhanced with LLM)
        # Split on connectors
        connectors = [" and ", " or ", " also ", " what about ", " how about "]
        expanded = [query]
        
        for connector in connectors:
            if connector in query.lower():
                parts = query.split(connector)
                expanded.extend([part.strip() for part in parts if part.strip()])
        
        return expanded[:3]  # Limit to 3 sub-queries
    
    async def _rewrite_query(self, query: str, history: Optional[List]) -> str:
        """Rewrite query using conversation context."""
        if not history or len(history) < 2:
            return query
        
        # Build context from history
        # Handle both dict and LangChain message objects
        context_parts = []
        for msg in history[-4:]:  # Last 4 messages
            if isinstance(msg, dict):
                role = msg.get('role', 'user')
                content = msg.get('content', '')[:100]
            else:
                # LangChain message object (HumanMessage, AIMessage, etc.)
                role = msg.__class__.__name__.replace('Message', '').lower()
                if hasattr(msg, 'content'):
                    content = str(msg.content)[:100]
                else:
                    content = str(msg)[:100]
            context_parts.append(f"{role}: {content}")
        context = "\n".join(context_parts)
        
        # Use LLM to rewrite query with context
        try:
            system_prompt = """You are a query rewriting assistant. Rewrite the user's query to be more specific and clear for document retrieval, using context from the conversation history if needed.
            
Return only the rewritten query, nothing else."""
            
            prompt = f"""Conversation context:
{context}

User query: {query}

Rewritten query:"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            rewritten = response.content.strip()
            
            logger.info(f"QueryRouter: Rewritten '{query}' → '{rewritten}'")
            return rewritten
            
        except Exception as e:
            logger.error(f"QueryRouter: Error rewriting query: {e}", exc_info=True)
            return query  # Return original on error

