from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    content = Column(Text, nullable=False)
    meta = Column("metadata", JSON, default={})  # metadata column in DB
    embedding = Column(Vector(1536))  # pgvector type
    source = Column(String(50), default='s3')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
