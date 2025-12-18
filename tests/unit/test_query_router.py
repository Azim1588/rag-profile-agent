"""Unit tests for query router."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.modular_rag.query_router import QueryRouter, QueryType


@pytest.mark.unit
class TestQueryRouter:
    """Test cases for QueryRouter."""
    
    @pytest.fixture
    def query_router(self):
        """Create a QueryRouter instance."""
        return QueryRouter()
    
    def test_classify_greeting(self, query_router):
        """Test classification of greeting queries."""
        query_type = query_router._classify_query_type("hello", history=None)
        
        assert query_type == QueryType.GREETING
    
    def test_classify_out_of_scope(self, query_router):
        """Test classification of out-of-scope queries."""
        # Test with clear out-of-scope queries that should not trigger factual Q&A
        test_cases = [
            ("tell me a joke", QueryType.OUT_OF_SCOPE),
            ("what is the weather today?", QueryType.OUT_OF_SCOPE),
            ("what time is it?", QueryType.OUT_OF_SCOPE),
        ]
        
        for query, expected_type in test_cases:
            query_type = query_router._classify_query_type(query.lower(), history=None)
            assert query_type == expected_type, f"Query '{query}' should be {expected_type}, got {query_type}"
    
    def test_classify_factual_qa(self, query_router):
        """Test classification of factual Q&A queries."""
        query_type = query_router._classify_query_type("What is Azim's education background?", history=None)
        
        assert query_type == QueryType.FACTUAL_QA
    
    @pytest.mark.asyncio
    async def test_analyze_query(self, query_router):
        """Test query analysis."""
        analysis = await query_router.analyze("What is Azim's education?")
        
        assert analysis.query_type in [QueryType.FACTUAL_QA, QueryType.CONVERSATIONAL]
        assert analysis.retrieval_strategy is not None
    
    @pytest.mark.asyncio
    async def test_analyze_greeting_skips_retrieval(self, query_router):
        """Test that greetings skip retrieval."""
        analysis = await query_router.analyze("hello")
        
        assert analysis.query_type == QueryType.GREETING
        assert analysis.retrieval_strategy == "none"

