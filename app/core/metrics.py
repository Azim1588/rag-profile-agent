"""
Performance metrics and latency tracking.
"""
import time
import logging
import uuid
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    trace_id: str
    session_id: str
    user_id: Optional[str] = None
    
    # Timing breakdowns
    start_time: float = field(default_factory=time.time)
    retrieval_time_ms: Optional[float] = None
    embedding_time_ms: Optional[float] = None
    llm_time_ms: Optional[float] = None
    first_token_time_ms: Optional[float] = None
    total_time_ms: Optional[float] = None
    
    # Request details
    query: Optional[str] = None
    retrieved_docs_count: int = 0
    response_length: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for logging."""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "query": self.query[:100] if self.query else None,  # Truncate long queries
            "retrieval_time_ms": self.retrieval_time_ms,
            "embedding_time_ms": self.embedding_time_ms,
            "llm_time_ms": self.llm_time_ms,
            "first_token_time_ms": self.first_token_time_ms,
            "total_time_ms": self.total_time_ms,
            "retrieved_docs_count": self.retrieved_docs_count,
            "response_length": self.response_length,
        }
    
    def emit(self, level: str = "INFO"):
        """Emit metrics as structured JSON log."""
        metrics_dict = self.to_dict()
        log_message = json.dumps(metrics_dict)
        
        if level == "INFO":
            logger.info(f"METRICS: {log_message}")
        elif level == "WARNING":
            logger.warning(f"METRICS: {log_message}")
        else:
            logger.error(f"METRICS: {log_message}")


class MetricsCollector:
    """Context manager for collecting request metrics."""
    
    def __init__(self, session_id: str, user_id: Optional[str] = None, query: Optional[str] = None):
        self.metrics = RequestMetrics(
            trace_id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            query=query
        )
        self._embedding_start: Optional[float] = None
        self._retrieval_start: Optional[float] = None
        self._llm_start: Optional[float] = None
        self._first_token_sent: bool = False
    
    def start_embedding(self):
        """Mark start of embedding generation."""
        self._embedding_start = time.time()
    
    def end_embedding(self):
        """Mark end of embedding generation."""
        if self._embedding_start:
            self.metrics.embedding_time_ms = (time.time() - self._embedding_start) * 1000
    
    def start_retrieval(self):
        """Mark start of retrieval."""
        self._retrieval_start = time.time()
    
    def end_retrieval(self, doc_count: int = 0):
        """Mark end of retrieval."""
        if self._retrieval_start:
            self.metrics.retrieval_time_ms = (time.time() - self._retrieval_start) * 1000
            self.metrics.retrieved_docs_count = doc_count
    
    def start_llm(self):
        """Mark start of LLM generation."""
        self._llm_start = time.time()
    
    def end_llm(self):
        """Mark end of LLM generation."""
        if self._llm_start:
            self.metrics.llm_time_ms = (time.time() - self._llm_start) * 1000
    
    def record_first_token(self):
        """Record time to first token."""
        if not self._first_token_sent:
            self.metrics.first_token_time_ms = (time.time() - self.metrics.start_time) * 1000
            self._first_token_sent = True
    
    def finish(self, response_length: int = 0):
        """Finish metrics collection."""
        self.metrics.total_time_ms = (time.time() - self.metrics.start_time) * 1000
        self.metrics.response_length = response_length
        return self.metrics


@asynccontextmanager
async def track_request(session_id: str, user_id: Optional[str] = None, query: Optional[str] = None):
    """Context manager for tracking request metrics."""
    collector = MetricsCollector(session_id, user_id, query)
    try:
        yield collector
    finally:
        metrics = collector.finish()
        # Emit metrics
        metrics.emit()

