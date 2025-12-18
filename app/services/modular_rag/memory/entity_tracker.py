"""Entity tracking from conversation history."""
import logging
from typing import List, Dict, Any, Set
import re

logger = logging.getLogger(__name__)


class EntityTracker:
    """Tracks entities mentioned in conversation history."""
    
    # Common entity patterns for profile context
    ENTITY_PATTERNS = {
        "skills": [
            r"\b(Python|JavaScript|TypeScript|Java|C\+\+|Go|Rust|SQL|PostgreSQL|MongoDB|Redis|Docker|Kubernetes|AWS|GCP|Azure|FastAPI|Django|Flask|React|Vue|Angular|Node\.js|Express|TensorFlow|PyTorch|LangChain|LangGraph|OpenAI|GPT|LLM|RAG|NLP|ML|AI|Data Engineering|Backend|Frontend|Full Stack)\b",
        ],
        "companies": [
            r"\b([A-Z][a-z]+ (?:Inc|Corp|LLC|Ltd|Company|Technologies|Systems))\b",
        ],
        "roles": [
            r"\b(Software Engineer|Backend Engineer|Frontend Engineer|Full Stack Engineer|AI Engineer|Data Engineer|ML Engineer|DevOps Engineer|SRE|Product Manager|Technical Lead|Senior|Junior|Intern|Developer|Programmer)\b",
        ],
        "projects": [
            r"\b(project|system|application|platform|service|API|tool|framework|library|agent|assistant|RAG|chatbot|dashboard)\b",
        ],
        "technologies": [
            r"\b(PostgreSQL|MySQL|MongoDB|Redis|Elasticsearch|Docker|Kubernetes|AWS|GCP|Azure|S3|EC2|Lambda|API Gateway|CloudFront|SQS|SNS|Celery|RabbitMQ)\b",
        ]
    }
    
    def extract(self, conversation_history: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        """
        Extract entities from conversation history.
        
        Args:
            conversation_history: List of message dicts with 'role' and 'content'
        
        Returns:
            Dictionary mapping entity types to sets of entities
        """
        entities: Dict[str, Set[str]] = {
            "skills": set(),
            "companies": set(),
            "roles": set(),
            "projects": set(),
            "technologies": set()
        }
        
        # Extract text from all messages
        all_text = " ".join([
            msg.get("content", "") for msg in conversation_history
            if isinstance(msg.get("content"), str)
        ])
        
        # Extract entities using patterns
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, all_text, re.IGNORECASE)
                entities[entity_type].update([m.lower() if isinstance(m, str) else str(m).lower() for m in matches])
        
        # Convert sets to lists for JSON serialization
        return {k: list(v) for k, v in entities.items() if v}
    
    def extract_recent_entities(self, conversation_history: List[Dict[str, Any]], n_messages: int = 5) -> Dict[str, Set[str]]:
        """
        Extract entities from recent messages only.
        
        Args:
            conversation_history: List of message dicts
            n_messages: Number of recent messages to consider
        
        Returns:
            Dictionary mapping entity types to sets of entities
        """
        recent_history = conversation_history[-n_messages:] if len(conversation_history) > n_messages else conversation_history
        return self.extract(recent_history)

