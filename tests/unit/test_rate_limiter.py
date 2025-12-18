"""Unit tests for rate limiter service."""
import pytest
from unittest.mock import AsyncMock, patch
from app.services.rate_limiter import RateLimiter


@pytest.mark.unit
class TestRateLimiter:
    """Test cases for RateLimiter service."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create a RateLimiter instance."""
        return RateLimiter()
    
    @pytest.mark.asyncio
    async def test_first_message_allowed(self, rate_limiter, sample_session_id, mock_redis_client):
        """Test that first message is allowed."""
        rate_limiter._get_client = AsyncMock(return_value=mock_redis_client)
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock(return_value=True)
        
        is_allowed, error_msg, retry_after = await rate_limiter.check_rate_limit(sample_session_id)
        
        assert is_allowed is True
        assert error_msg is None
        assert retry_after is None
        mock_redis_client.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_under_limit_allowed(self, rate_limiter, sample_session_id, mock_redis_client):
        """Test that messages under limit are allowed."""
        rate_limiter._get_client = AsyncMock(return_value=mock_redis_client)
        mock_redis_client.get = AsyncMock(return_value="3")  # 3 messages sent
        mock_redis_client.incr = AsyncMock(return_value=4)
        
        is_allowed, error_msg, retry_after = await rate_limiter.check_rate_limit(sample_session_id)
        
        assert is_allowed is True
        assert error_msg is None
        mock_redis_client.incr.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_limit_exceeded(self, rate_limiter, sample_session_id, mock_redis_client):
        """Test that limit exceeded returns error."""
        rate_limiter._get_client = AsyncMock(return_value=mock_redis_client)
        mock_redis_client.get = AsyncMock(return_value="5")  # 5 messages (at limit)
        mock_redis_client.ttl = AsyncMock(return_value=21600)  # 6 hours remaining
        
        is_allowed, error_msg, retry_after = await rate_limiter.check_rate_limit(sample_session_id)
        
        assert is_allowed is False
        assert error_msg is not None
        assert "reached the allowed message limit" in error_msg
        assert retry_after == 21600
    
    @pytest.mark.asyncio
    async def test_expired_limit_resets(self, rate_limiter, sample_session_id, mock_redis_client):
        """Test that expired limit resets counter."""
        rate_limiter._get_client = AsyncMock(return_value=mock_redis_client)
        mock_redis_client.get = AsyncMock(return_value="5")
        mock_redis_client.ttl = AsyncMock(return_value=-1)  # Expired
        mock_redis_client.setex = AsyncMock(return_value=True)
        
        is_allowed, error_msg, retry_after = await rate_limiter.check_rate_limit(sample_session_id)
        
        assert is_allowed is True
        assert error_msg is None
        mock_redis_client.setex.assert_called_once()  # Reset counter
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_status(self, rate_limiter, sample_session_id, mock_redis_client):
        """Test getting rate limit status."""
        rate_limiter._get_client = AsyncMock(return_value=mock_redis_client)
        mock_redis_client.get = AsyncMock(return_value="3")
        mock_redis_client.ttl = AsyncMock(return_value=18000)
        
        status = await rate_limiter.get_rate_limit_status(sample_session_id)
        
        assert status["session_id"] == sample_session_id
        assert status["messages_used"] == 3
        assert status["messages_remaining"] == 2  # 5 - 3
        assert status["limit_reset_seconds"] == 18000
        assert status["is_limited"] is False
    
    @pytest.mark.asyncio
    async def test_redis_failure_fails_open(self, rate_limiter, sample_session_id, mock_redis_client):
        """Test that Redis failure allows request (fail-open policy)."""
        rate_limiter._get_client = AsyncMock(return_value=mock_redis_client)
        mock_redis_client.get = AsyncMock(side_effect=Exception("Redis connection failed"))
        
        is_allowed, error_msg, retry_after = await rate_limiter.check_rate_limit(sample_session_id)
        
        # Should fail open - allow the request
        assert is_allowed is True
        assert error_msg is None
    
    @pytest.mark.asyncio
    async def test_reset_rate_limit(self, rate_limiter, sample_session_id, mock_redis_client):
        """Test resetting rate limit for a session."""
        rate_limiter._get_client = AsyncMock(return_value=mock_redis_client)
        mock_redis_client.delete = AsyncMock(return_value=1)
        
        result = await rate_limiter.reset_rate_limit(sample_session_id)
        
        assert result is True
        mock_redis_client.delete.assert_called_once()

