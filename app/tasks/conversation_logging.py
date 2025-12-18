"""
Background task for logging conversation messages to PostgreSQL.
Makes DB writes non-blocking for the hot path.
"""
import asyncio
from typing import Optional
from app.tasks.celery_app import celery_app
from app.core.database import get_async_session
from app.models.conversation import Conversation, Message
from sqlalchemy import select
import uuid


@celery_app.task(name="app.tasks.conversation_logging.log_user_message")
def log_user_message(
    conversation_id: str,
    user_id: str,
    content: str
):
    """Log user message to PostgreSQL in background."""
    try:
        # Always create a fresh event loop for Celery tasks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_async_log_user_message(conversation_id, user_id, content))
        finally:
            loop.close()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to log user message in Celery task: {e}", exc_info=True)


@celery_app.task(name="app.tasks.conversation_logging.log_assistant_message")
def log_assistant_message(
    conversation_id: str,
    content: str
):
    """Log assistant message to PostgreSQL in background."""
    try:
        # Always create a fresh event loop for Celery tasks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_async_log_assistant_message(conversation_id, content))
        finally:
            loop.close()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to log assistant message in Celery task: {e}", exc_info=True)


async def _async_log_user_message(conversation_id: str, user_id: str, content: str):
    """Async implementation of logging user message."""
    async with get_async_session() as session:
        try:
            conv_id = uuid.UUID(conversation_id)
            user_message = Message(
                conversation_id=conv_id,
                role="user",
                content=content
            )
            session.add(user_message)
            await session.commit()
        except Exception as e:
            # Log error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to log user message: {e}", exc_info=True)
            await session.rollback()


async def _async_log_assistant_message(conversation_id: str, content: str):
    """Async implementation of logging assistant message."""
    async with get_async_session() as session:
        try:
            conv_id = uuid.UUID(conversation_id)
            assistant_message = Message(
                conversation_id=conv_id,
                role="assistant",
                content=content
            )
            session.add(assistant_message)
            await session.commit()
        except Exception as e:
            # Log error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to log assistant message: {e}", exc_info=True)
            await session.rollback()

