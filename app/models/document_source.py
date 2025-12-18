from sqlalchemy import Column, String, DateTime, BigInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class DocumentSource(Base):
    """Model for tracking document sources (S3 files) for incremental ingestion."""
    __tablename__ = "document_sources"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    s3_key = Column(String(1024), unique=True, nullable=False, index=True)  # S3 keys can be long
    etag = Column(String(64))
    last_modified = Column(DateTime(timezone=True))
    file_hash = Column(String(64))
    file_size = Column(BigInteger)
    status = Column(String(20), default='pending', index=True)  # synced, pending, failed, processing
    synced_at = Column(DateTime(timezone=True), index=True)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

