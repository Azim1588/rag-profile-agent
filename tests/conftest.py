"""Pytest configuration and shared fixtures."""
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
import os

# Set test environment variables before importing app
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "True"
os.environ["OPENAI_API_KEY"] = "test-key-123"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-purposes-only-32-chars-min"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["REDIS_HOST"] = "localhost"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test_db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Use DB 15 for testing


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.setex = AsyncMock(return_value=True)
    mock_client.incr = AsyncMock(return_value=1)
    mock_client.decr = AsyncMock(return_value=0)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.exists = AsyncMock(return_value=0)
    mock_client.ttl = AsyncMock(return_value=-1)
    mock_client.expire = AsyncMock(return_value=True)
    mock_client.lpush = AsyncMock(return_value=1)
    mock_client.lrange = AsyncMock(return_value=[])
    mock_client.llen = AsyncMock(return_value=0)
    mock_client.ltrim = AsyncMock(return_value=True)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()
    return mock_client


@pytest.fixture
def mock_postgres_session():
    """Mock PostgreSQL async session for testing."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.close = AsyncMock()
    
    # Context manager support
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    
    return mock_session


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = MagicMock()
    mock_response = AsyncMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "Test response"
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.fixture
def sample_session_id():
    """Sample session ID for testing."""
    return "test-session-12345"


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return "test-user-12345"


@pytest.fixture
def sample_conversation_id():
    """Sample conversation ID for testing."""
    return "test-conversation-12345"


@pytest.fixture
def sample_query():
    """Sample query for testing."""
    return "What is Azim's education background?"


@pytest.fixture
def mock_vector_store():
    """Mock vector store service."""
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[])
    mock_store.add_document = AsyncMock(return_value=True)
    mock_store.get_document = AsyncMock(return_value=None)
    return mock_store


@pytest.fixture
def mock_langchain_messages():
    """Mock LangChain messages."""
    from langchain_core.messages import HumanMessage, AIMessage
    
    return [
        HumanMessage(content="Hello"),
        AIMessage(content="Hi! How can I help?"),
        HumanMessage(content="Tell me about Azim"),
    ]


@pytest.fixture
def test_client():
    """Create a test client for FastAPI."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    return TestClient(app)


@pytest.fixture
async def async_test_client():
    """Create an async test client for FastAPI."""
    from httpx import AsyncClient
    from app.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

