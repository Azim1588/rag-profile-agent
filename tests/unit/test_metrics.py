"""Unit tests for metrics collector."""
import pytest
import time
from app.core.metrics import MetricsCollector, RequestMetrics


@pytest.mark.unit
class TestMetricsCollector:
    """Test cases for MetricsCollector."""
    
    def test_metrics_collector_initialization(self, sample_session_id, sample_user_id):
        """Test MetricsCollector initialization."""
        collector = MetricsCollector(sample_session_id, sample_user_id, "test query")
        
        assert collector.metrics.session_id == sample_session_id
        assert collector.metrics.user_id == sample_user_id
        assert collector.metrics.query == "test query"
    
    def test_start_retrieval(self, sample_session_id, sample_user_id):
        """Test starting retrieval timing."""
        collector = MetricsCollector(sample_session_id, sample_user_id, "test query")
        
        collector.start_retrieval()
        
        assert collector._retrieval_start is not None
    
    def test_end_retrieval(self, sample_session_id, sample_user_id):
        """Test ending retrieval timing."""
        collector = MetricsCollector(sample_session_id, sample_user_id, "test query")
        
        collector.start_retrieval()
        time.sleep(0.01)  # Small delay
        collector.end_retrieval(5)
        
        assert collector.metrics.retrieved_docs_count == 5
        assert collector.metrics.retrieval_time_ms is not None
        assert collector.metrics.retrieval_time_ms > 0
    
    def test_start_llm(self, sample_session_id, sample_user_id):
        """Test starting LLM timing."""
        collector = MetricsCollector(sample_session_id, sample_user_id, "test query")
        
        collector.start_llm()
        
        assert collector._llm_start is not None
    
    def test_end_llm(self, sample_session_id, sample_user_id):
        """Test ending LLM timing."""
        collector = MetricsCollector(sample_session_id, sample_user_id, "test query")
        
        collector.start_llm()
        time.sleep(0.01)  # Small delay
        collector.end_llm()
        
        assert collector.metrics.llm_time_ms is not None
        assert collector.metrics.llm_time_ms > 0
    
    def test_record_first_token(self, sample_session_id, sample_user_id):
        """Test recording first token time."""
        collector = MetricsCollector(sample_session_id, sample_user_id, "test query")
        
        collector.start_llm()
        collector.record_first_token()
        
        assert collector.metrics.first_token_time_ms is not None
        assert collector.metrics.first_token_time_ms >= 0
    
    def test_finish(self, sample_session_id, sample_user_id):
        """Test finishing metrics collection."""
        collector = MetricsCollector(sample_session_id, sample_user_id, "test query")
        
        collector.start_retrieval()
        collector.end_retrieval(3)
        collector.start_llm()
        collector.end_llm()
        
        metrics = collector.finish(100)
        
        assert isinstance(metrics, RequestMetrics)
        assert metrics.retrieved_docs_count == 3
        assert metrics.response_length == 100
        assert metrics.retrieval_time_ms is not None
        assert metrics.llm_time_ms is not None

