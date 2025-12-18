"""Chat request and response schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class ChatMessage(BaseModel):
    """Chat message schema."""
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat request schema."""
    message: str = Field(..., description="User message")
    session_id: Optional[UUID] = Field(None, description="Session ID for conversation continuity")
    user_id: Optional[str] = Field(None, description="User ID")
    stream: bool = Field(False, description="Whether to stream the response")


class ChatResponse(BaseModel):
    """Chat response schema."""
    message: str = Field(..., description="Assistant response")
    session_id: UUID = Field(..., description="Session ID")
    conversation_id: Optional[UUID] = Field(None, description="Conversation ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

