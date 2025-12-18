from langgraph.graph import StateGraph, END

from app.services.langgraph.state import AgentState
from app.services.langgraph.nodes import AgentNodes
from app.services.vector_store import VectorStoreService
from app.services.redis_memory import redis_memory_service
from app.core.config import settings


class RAGAgent:
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.nodes = AgentNodes(self.vector_store)
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("understand_query", self.nodes.understand_query)
        workflow.add_node("retrieve_context", self.nodes.retrieve_context)
        workflow.add_node("generate_response", self.nodes.generate_response)
        
        # Define edges (flow)
        workflow.set_entry_point("understand_query")
        
        workflow.add_conditional_edges(
            "understand_query",
            lambda state: "retrieve" if state["should_retrieve"] else "generate",
            {
                "retrieve": "retrieve_context",
                "generate": "generate_response"
            }
        )
        
        workflow.add_edge("retrieve_context", "generate_response")
        workflow.add_edge("generate_response", END)
        
        # Add checkpointer for state persistence (optional)
        # Note: PostgresSaver requires proper setup and is optional
        # The system works fine without it - state just won't persist across restarts
        # For now, we'll disable it to avoid complexity
        # TODO: Implement proper PostgresSaver initialization if needed
        return workflow.compile()
    
    async def invoke(
        self,
        query: str,
        user_id: str,
        session_id: str,
        conversation_history: list = None,
        metadata_filters: dict = None
    ) -> dict:
        """Invoke the agent with a query"""
        # Get recent session memory from Redis if conversation_history not provided
        if conversation_history is None:
            try:
                redis_messages = await redis_memory_service.get_session_memory(session_id, limit=10)
                conversation_history = redis_messages
            except Exception as e:
                print(f"Error loading Redis memory: {e}")
                conversation_history = []
        
        initial_state = {
            "query": query,
            "user_id": user_id,
            "session_id": session_id,
            "messages": conversation_history or [],
            "retrieved_documents": None,
            "metadata_filters": metadata_filters,
            "response": None,
            "grounding_result": None,
            "should_retrieve": True,
            "needs_clarification": False
        }
        
        # Run the graph
        result = await self.graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": session_id}}
        )
        
        return result
    
    async def stream(
        self,
        query: str,
        user_id: str,
        session_id: str,
        conversation_history: list = None,
        metadata_filters: dict = None
    ):
        """Stream the agent response"""
        # Get recent session memory from Redis if conversation_history not provided
        if conversation_history is None:
            try:
                redis_messages = await redis_memory_service.get_session_memory(session_id, limit=10)
                conversation_history = redis_messages
            except Exception as e:
                print(f"Error loading Redis memory: {e}")
                conversation_history = []
        
        initial_state = {
            "query": query,
            "user_id": user_id,
            "session_id": session_id,
            "messages": conversation_history or [],
            "retrieved_documents": None,
            "metadata_filters": metadata_filters,
            "response": None,
            "grounding_result": None,
            "should_retrieve": True,
            "needs_clarification": False
        }
        
        # Stream the graph execution
        async for chunk in self.graph.astream(
            initial_state,
            config={"configurable": {"thread_id": session_id}}
        ):
            yield chunk
