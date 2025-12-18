"""
Analytics tracking tasks for Celery.
Logs query events, response metrics, and system performance.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import text
import asyncio

from app.tasks.celery_app import celery_app
from app.core.database import get_async_session
import json


@celery_app.task(name="app.tasks.analytics.log_query_event")
def log_query_event(
    event_type: str,
    event_data: Dict[str, Any],
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Log a query event to the analytics table.
    
    Args:
        event_type: Type of event (e.g., 'query', 'response', 'error')
        event_data: Dictionary containing event details
        user_id: Optional user identifier
        session_id: Optional session identifier
    """
    try:
        # Always create a fresh event loop for Celery tasks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_async_log_query_event(event_type, event_data, user_id, session_id))
        finally:
            loop.close()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to log query event in Celery task: {e}", exc_info=True)


async def _async_log_query_event(
    event_type: str,
    event_data: Dict[str, Any],
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """Async implementation of logging query event."""
    # Add metadata
    enriched_data = {
        **event_data,
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    async with get_async_session() as session:
        try:
            # Insert into analytics table
            await session.execute(
                text("""
                    INSERT INTO analytics (event_type, event_data, created_at)
                    VALUES (:event_type, :event_data::jsonb, :created_at)
                """),
                {
                    "event_type": event_type,
                    "event_data": json.dumps(enriched_data),  # Proper JSON conversion
                    "created_at": datetime.utcnow()
                }
            )
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"Error logging analytics event: {e}")


@celery_app.task(name="app.tasks.analytics.log_query_metrics")
def log_query_metrics(
    query: str,
    response_time_ms: float,
    retrieved_docs_count: int,
    response_length: int,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    has_grounding: bool = False,
    similarity_scores: Optional[list] = None
):
    """
    Log detailed query metrics for analytics.
    
    Args:
        query: User query text
        response_time_ms: Response time in milliseconds
        retrieved_docs_count: Number of documents retrieved
        response_length: Length of response in characters
        user_id: Optional user identifier
        session_id: Optional session identifier
        has_grounding: Whether grounding verification was performed
        similarity_scores: List of similarity scores for retrieved docs
    """
    event_data = {
        "query": query[:200],  # Truncate long queries
        "response_time_ms": response_time_ms,
        "retrieved_docs_count": retrieved_docs_count,
        "response_length": response_length,
        "has_grounding": has_grounding,
        "similarity_scores": similarity_scores or []
    }
    
    log_query_event.delay(
        event_type="query_metrics",
        event_data=event_data,
        user_id=user_id,
        session_id=session_id
    )


@celery_app.task(name="app.tasks.analytics.log_error_event")
def log_error_event(
    error_type: str,
    error_message: str,
    context: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Log error events for monitoring and debugging.
    
    Args:
        error_type: Type of error (e.g., 'embedding_error', 'llm_error', 'db_error')
        error_message: Error message
        context: Additional context about the error
        user_id: Optional user identifier
        session_id: Optional session identifier
    """
    event_data = {
        "error_type": error_type,
        "error_message": error_message,
        "context": context or {}
    }
    
    log_query_event.delay(
        event_type="error",
        event_data=event_data,
        user_id=user_id,
        session_id=session_id
    )

