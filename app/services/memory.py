"""Conversation memory service."""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.conversation import Conversation, Message


class MemoryService:
    """Service for managing conversation memory."""
    
    async def get_or_create_conversation(
        self,
        db: AsyncSession,
        user_id: str,
        session_id: UUID,
    ) -> Conversation:
        """Get or create a conversation."""
        query = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.session_id == session_id,
        )
        result = await db.execute(query)
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            conversation = Conversation(
                user_id=user_id,
                session_id=session_id,
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)
        
        return conversation
    
    async def add_message(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        role: str,
        content: str,
        metadata: dict = None,
    ) -> Message:
        """Add a message to a conversation."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata or {},
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        return message
    
    async def get_conversation_history(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        limit: int = 50,
    ) -> List[Message]:
        """Get conversation history."""
        query = select(Message).where(
            Message.conversation_id == conversation_id
        ).order_by(
            Message.created_at.desc()
        ).limit(limit)
        
        result = await db.execute(query)
        messages = result.scalars().all()
        return list(reversed(messages))


memory_service = MemoryService()

