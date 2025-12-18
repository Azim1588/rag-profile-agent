"""Enhanced conversation memory with entity tracking and topic extraction."""
import logging
from typing import List, Dict, Any, Optional
from collections import Counter

from app.services.modular_rag.memory.entity_tracker import EntityTracker
from app.services.redis_memory import redis_memory_service

logger = logging.getLogger(__name__)


class EnhancedConversationMemory:
    """Enhanced memory with entity tracking, topic extraction, and intent inference."""
    
    def __init__(self, redis_memory_service_instance=None):
        """
        Initialize enhanced memory.
        
        Args:
            redis_memory_service_instance: Redis memory service instance
        """
        self.redis_memory = redis_memory_service_instance or redis_memory_service
        self.entity_tracker = EntityTracker()
    
    async def get_enriched_context(
        self,
        conversation_id: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get enriched conversation context with entities, topics, and intent.
        
        Args:
            conversation_id: Session/conversation ID
            limit: Maximum number of messages to retrieve
        
        Returns:
            Dictionary with:
            - history: List of messages
            - entities: Extracted entities by type
            - topics: Extracted topics
            - user_intent: Inferred user intent
        """
        # Get conversation history from Redis
        history = await self.redis_memory.get_session_memory(conversation_id, limit=limit)
        
        if not history:
            return {
                "history": [],
                "entities": {},
                "topics": [],
                "user_intent": "unknown"
            }
        
        # Extract entities
        entities = self.entity_tracker.extract(history)
        
        # Extract topics (simple keyword-based for now)
        topics = self._extract_topics(history)
        
        # Infer intent
        intent = self._infer_intent(history)
        
        logger.info(
            f"EnhancedMemory: Enriched context for {conversation_id}: "
            f"{len(history)} messages, {len(entities)} entity types, "
            f"{len(topics)} topics, intent={intent}"
        )
        
        return {
            "history": history,
            "entities": entities,
            "topics": topics,
            "user_intent": intent
        }
    
    def _extract_topics(self, history: List[Dict[str, Any]]) -> List[str]:
        """
        Extract topics from conversation history.
        
        Simple keyword-based topic extraction.
        Can be enhanced with LLM or NLP libraries.
        
        Args:
            history: List of message dicts
        
        Returns:
            List of topic strings
        """
        # Topic keywords
        topic_keywords = {
            "work_experience": ["experience", "worked", "job", "position", "role", "career", "employment"],
            "education": ["education", "degree", "university", "college", "graduated", "studied"],
            "skills": ["skills", "technologies", "tools", "programming", "languages", "frameworks"],
            "projects": ["project", "built", "developed", "created", "system", "application"],
            "interests": ["interested", "passionate", "enjoy", "like", "favorite", "hobby"],
            "goals": ["goal", "aspire", "want", "aim", "plan", "future", "looking for"]
        }
        
        # Extract text from all messages
        all_text = " ".join([
            msg.get("content", "").lower() for msg in history
            if isinstance(msg.get("content"), str)
        ])
        
        # Count keyword matches
        topic_scores = {}
        for topic, keywords in topic_keywords.items():
            score = sum(1 for keyword in keywords if keyword in all_text)
            if score > 0:
                topic_scores[topic] = score
        
        # Return top topics (sorted by score)
        topics = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, score in topics[:5]]  # Top 5 topics
    
    def _infer_intent(self, history: List[Dict[str, Any]]) -> str:
        """
        Infer user intent from conversation history.
        
        Args:
            history: List of message dicts
        
        Returns:
            Intent string
        """
        if not history:
            return "unknown"
        
        # Get last user message
        user_messages = [msg for msg in history if msg.get("role") == "user"]
        if not user_messages:
            return "unknown"
        
        last_user_message = user_messages[-1].get("content", "").lower()
        
        # Intent patterns
        intent_patterns = {
            "information_seeking": ["what", "tell me", "describe", "explain", "how", "when", "where", "who"],
            "comparison": ["compare", "difference", "vs", "versus", "better", "prefer"],
            "clarification": ["clarify", "what do you mean", "can you explain", "not sure"],
            "recommendation": ["recommend", "suggest", "should", "best", "good", "better"],
            "confirmation": ["confirm", "is it", "are you", "do you", "can you", "will you"]
        }
        
        # Match intent patterns
        for intent, patterns in intent_patterns.items():
            if any(pattern in last_user_message for pattern in patterns):
                return intent
        
        return "information_seeking"  # Default intent
    
    async def add_entities_to_query(
        self,
        query: str,
        conversation_id: str
    ) -> str:
        """
        Enhance query with relevant entities from conversation history.
        
        Args:
            query: Original query
            conversation_id: Session ID
        
        Returns:
            Enhanced query with entity context
        """
        enriched = await self.get_enriched_context(conversation_id)
        entities = enriched.get("entities", {})
        
        if not entities:
            return query
        
        # Extract relevant entity mentions to add to query
        # For now, just append skill entities if query is about skills
        if any(word in query.lower() for word in ["skill", "technology", "tool", "language", "framework"]):
            skills = entities.get("skills", [])
            if skills:
                # Add top skills as context
                query += " " + " ".join(skills[:3])
        
        return query

