from typing import TypedDict, List, Optional, Dict, Any
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """State schema for LangGraph agent"""
    # Input
    query: str
    user_id: str
    session_id: str
    
    # Conversation history
    messages: List[BaseMessage]
    
    # RAG context
    retrieved_documents: Optional[List[dict]]
    metadata_filters: Optional[Dict[str, Any]]  # For filtering retrieval by metadata
    
    # Generation
    response: Optional[str]
    grounding_result: Optional[Dict[str, Any]]  # Grounding verification results
    
    # Metadata
    should_retrieve: bool
    needs_clarification: bool
