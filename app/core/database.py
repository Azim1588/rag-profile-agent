from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

from app.core.config import settings

# Get database URL - environment variables from docker-compose override .env
DATABASE_URL = settings.get_database_url()

# Log the connection string (without password) for debugging
import logging
logger = logging.getLogger(__name__)
# Mask password in log
masked_url = DATABASE_URL.split('@')[0].split(':')[-1] + '@' + '@'.join(DATABASE_URL.split('@')[1:]) if '@' in DATABASE_URL else DATABASE_URL
logger.info(f"Database connection URL: {masked_url}")

engine = create_async_engine(
    DATABASE_URL,
    echo=True if os.getenv("DEBUG") == "True" else False,
    pool_size=20,  # Connection pool size
    max_overflow=10,  # Additional connections beyond pool_size
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
    connect_args={
        "server_settings": {
            "application_name": "rag_profile_agent",
            "tcp_keepalives_idle": "600",
            "tcp_keepalives_interval": "30",
            "tcp_keepalives_count": "3",
        }
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


@asynccontextmanager
async def get_async_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_db():
    async with get_async_session() as session:
        yield session

