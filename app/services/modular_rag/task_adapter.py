"""Task adapter for configuring retrieval and generation based on query type."""
import logging
from typing import Dict, Any, Optional
from enum import Enum

from app.services.modular_rag.query_router import QueryType

logger = logging.getLogger(__name__)


class TaskConfig:
    """Configuration for a specific task type."""
    
    def __init__(
        self,
        retrieval_k: int = 5,
        rerank: bool = True,
        citation_required: bool = True,
        temperature: float = 0.7,
        strategy: str = "hybrid",
        memory_weight: float = 0.5,
        max_tokens: Optional[int] = None,
        compression: str = "none"  # "none", "moderate", "aggressive"
    ):
        self.retrieval_k = retrieval_k
        self.rerank = rerank
        self.citation_required = citation_required
        self.temperature = temperature
        self.strategy = strategy
        self.memory_weight = memory_weight
        self.max_tokens = max_tokens
        self.compression = compression


class TaskAdapter:
    """Adapts retrieval and generation parameters based on query/task type."""
    
    # Task-specific configurations
    TASK_CONFIGS: Dict[QueryType, TaskConfig] = {
        QueryType.FACTUAL_QA: TaskConfig(
            retrieval_k=5,
            rerank=True,
            citation_required=True,
            temperature=0.1,  # Low temperature for factual accuracy
            strategy="hybrid",
            memory_weight=0.3,
            max_tokens=300,
            compression="moderate"
        ),
        QueryType.CONVERSATIONAL: TaskConfig(
            retrieval_k=3,
            rerank=False,  # Faster for conversational flow
            citation_required=False,
            temperature=0.7,  # More natural conversation
            strategy="dense",  # Dense retrieval better for context
            memory_weight=0.7,  # Heavy weight on conversation history
            max_tokens=400,
            compression="none"
        ),
        QueryType.MULTI_HOP: TaskConfig(
            retrieval_k=10,  # More documents needed for multi-hop
            rerank=True,
            citation_required=True,
            temperature=0.3,
            strategy="hybrid",
            memory_weight=0.4,
            max_tokens=500,
            compression="moderate"
        ),
        QueryType.SUMMARIZATION: TaskConfig(
            retrieval_k=20,  # Need more context for summarization
            rerank=True,
            citation_required=True,
            temperature=0.3,  # Lower temperature for factual summary
            strategy="hybrid",
            memory_weight=0.2,
            max_tokens=600,
            compression="aggressive"  # Compress to fit more context
        ),
        QueryType.CLARIFICATION: TaskConfig(
            retrieval_k=3,
            rerank=False,
            citation_required=False,
            temperature=0.5,
            strategy="dense",
            memory_weight=0.8,  # Heavy on recent context
            max_tokens=200,
            compression="none"
        )
    }
    
    # Default configuration
    DEFAULT_CONFIG = TaskConfig(
        retrieval_k=5,
        rerank=True,
        citation_required=True,
        temperature=0.7,
        strategy="hybrid",
        memory_weight=0.5,
        max_tokens=300,
        compression="moderate"
    )
    
    def adapt(self, query_type: QueryType) -> TaskConfig:
        """
        Get task-specific configuration.
        
        Args:
            query_type: The type of query/task
        
        Returns:
            TaskConfig object with adapted parameters
        """
        config = self.TASK_CONFIGS.get(query_type, self.DEFAULT_CONFIG)
        logger.info(f"TaskAdapter: Adapted config for {query_type.value}: "
                   f"k={config.retrieval_k}, rerank={config.rerank}, "
                   f"strategy={config.strategy}, temp={config.temperature}")
        return config
    
    def get_retrieval_params(self, query_type: QueryType) -> Dict[str, Any]:
        """
        Get retrieval parameters for a task type.
        
        Returns:
            Dictionary with retrieval parameters
        """
        config = self.adapt(query_type)
        return {
            "top_k": config.retrieval_k,
            "rerank": config.rerank,
            "strategy": config.strategy
        }
    
    def get_generation_params(self, query_type: QueryType) -> Dict[str, Any]:
        """
        Get generation parameters for a task type.
        
        Returns:
            Dictionary with generation parameters
        """
        config = self.adapt(query_type)
        params = {
            "temperature": config.temperature,
            "memory_weight": config.memory_weight,
            "citation_required": config.citation_required,
            "compression": config.compression
        }
        if config.max_tokens:
            params["max_tokens"] = config.max_tokens
        return params

