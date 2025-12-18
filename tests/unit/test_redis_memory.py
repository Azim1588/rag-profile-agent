"""Unit tests for Redis memory service."""
import pytest
import json
from unittest.mock import AsyncMock, patch
from app.services.redis_memory import RedisMemoryService


@pytest.mark.unit
class TestRedisMemoryService:
    """Test cases for RedisMemoryService."""
    
    @pytest.fixture
    def memory_service(self):
        """Create a RedisMemoryService instance."""
        return RedisMemoryService()
    
    @pytest.mark.asyncio
    async def test_add_to_session(self, memory_service, sample_session_id, mock_redis_client):
        """Test adding message to session."""
        memory_service._get_client = AsyncMock(return_value=mock_redis_client)
        mock_redis_client.lpush = AsyncMock(return_value=1)
        mock_redis_client.expire = AsyncMock(return_value=True)
        mock_redis_client.ltrim = AsyncMock(return_value=True)
        
        await memory_service.add_to_session(
            session_id=sample_session_id,
            role="user",
            content="Hello"
        )
        
        mock_redis_client.lpush.assert_called_once()
        mock_redis_client.expire.assert_called_once()
        mock_redis_client.ltrim.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_session_memory(self, memory_service, sample_session_id, mock_redis_client):
        """Test getting session memory."""
        memory_service._get_client = AsyncMock(return_value=mock_redis_client)
        sample_messages = [
            json.dumps({"role": "user", "content": "Hello", "timestamp": 1234567890}),
            json.dumps({"role": "assistant", "content": "Hi!", "timestamp": 1234567891}),
        ]
        mock_redis_client.lrange = AsyncMock(return_value=sample_messages)
        
        messages = await memory_service.get_session_memory(sample_session_id, limit=10)
        
        assert len(messages) == 2
        assert messages[0]["role"] == "assistant"  # Reversed order
        assert messages[1]["role"] == "user"
    
    @pytest.mark.asyncio
    async def test_get_session_memory_empty(self, memory_service, sample_session_id, mock_redis_client):
        """Test getting session memory when empty."""
        memory_service._get_client = AsyncMock(return_value=mock_redis_client)
        mock_redis_client.lrange = AsyncMock(return_value=[])
        
        messages = await memory_service.get_session_memory(sample_session_id)
        
        assert messages == []
    
    @pytest.mark.asyncio
    async def test_clear_session(self, memory_service, sample_session_id, mock_redis_client):
        """Test clearing session."""
        memory_service._get_client = AsyncMock(return_value=mock_redis_client)
        mock_redis_client.delete = AsyncMock(return_value=1)
        
        await memory_service.clear_session(sample_session_id)
        
        mock_redis_client.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_session_summary(self, memory_service, sample_session_id, mock_redis_client):
        """Test getting session summary."""
        memory_service._get_client = AsyncMock(return_value=mock_redis_client)
        mock_redis_client.llen = AsyncMock(return_value=5)
        mock_redis_client.ttl = AsyncMock(return_value=3600)
        
        summary = await memory_service.get_session_summary(sample_session_id)
        
        assert summary["session_id"] == sample_session_id
        assert summary["message_count"] == 5
        assert summary["ttl_seconds"] == 3600

