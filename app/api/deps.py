"""API dependencies for FastAPI endpoints."""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db


async def get_database() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async for session in get_db():
        yield session

