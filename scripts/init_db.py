"""Database initialization script."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import engine, Base
from app.models import document, conversation


async def init_db():
    """Initialize database schema."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Database schema created successfully")


if __name__ == "__main__":
    asyncio.run(init_db())

