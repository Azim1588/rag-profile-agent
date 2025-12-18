"""Document request and response schemas."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


class DocumentBase(BaseModel):
    """Base document schema."""
    filename: str = Field(..., description="Document filename")
    source: str = Field(default="s3", description="Document source")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class DocumentCreate(DocumentBase):
    """Document creation schema."""
    content: str = Field(..., description="Document content")
    content_hash: str = Field(..., description="Content hash for deduplication")


class DocumentResponse(DocumentBase):
    """Document response schema."""
    id: UUID = Field(..., description="Document ID")
    content_hash: str = Field(..., description="Content hash")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Document list response schema."""
    documents: List[DocumentResponse] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents")

