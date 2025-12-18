"""Rate limiting service for session-based message limiting."""
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta
import os

try:
    import redis.asyncio as redis
except ImportError:
    import redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Service for rate limiting based on session ID."""
    
    def __init__(self):
        """Initialize rate limiter with Redis connection."""
        self.redis_client: Optional[redis.Redis] = None
        self.max_messages = 5  # Maximum messages per session
        self.window_hours = 6  # Time window in hours
        self.window_seconds = self.window_hours * 3600  # Convert to seconds
    
    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self.redis_client is None:
            # Detect Docker environment
            is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
            
            if is_docker:
                host = 'redis'  # Docker service name
            else:
                host = settings.REDIS_HOST
            
            port = settings.REDIS_PORT
            db = settings.REDIS_DB + 4  # Use DB 4 for rate limiting (0=Celery, 1=results, 2=session, 3=cache)
            password = None  # Redis in docker-compose has no password
            
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=5
            )
        return self.redis_client
    
    async def check_rate_limit(self, session_id: str) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check if session can send a message.
        
        Args:
            session_id: The session ID to check
            
        Returns:
            Tuple of (is_allowed, error_message, retry_after_seconds)
            - is_allowed: True if message is allowed, False otherwise
            - error_message: Error message if limit exceeded, None otherwise
            - retry_after_seconds: Seconds until limit resets, None if allowed
        """
        try:
            client = await self._get_client()
            key = f"rate_limit:session:{session_id}"
            
            # Get current message count
            current_count = await client.get(key)
            
            if current_count is None:
                # First message, initialize counter with TTL
                await client.setex(key, self.window_seconds, "1")
                return True, None, None
            
            count = int(current_count)
            
            if count >= self.max_messages:
                # Limit exceeded, get TTL to tell user when they can retry
                ttl = await client.ttl(key)
                if ttl <= 0:
                    # TTL expired, reset counter
                    await client.setex(key, self.window_seconds, "1")
                    return True, None, None
                
                # Calculate retry time
                retry_after_seconds = ttl
                hours_remaining = retry_after_seconds // 3600
                minutes_remaining = (retry_after_seconds % 3600) // 60
                
                if hours_remaining > 0:
                    error_msg = f"You have reached the allowed message limit. Please try again after {hours_remaining} hour{'s' if hours_remaining != 1 else ''}."
                elif minutes_remaining > 0:
                    error_msg = f"You have reached the allowed message limit. Please try again after {minutes_remaining} minute{'s' if minutes_remaining != 1 else ''}."
                else:
                    error_msg = f"You have reached the allowed message limit. Please try again after {retry_after_seconds} second{'s' if retry_after_seconds != 1 else ''}."
                
                logger.warning(f"Rate limit exceeded for session {session_id}: {count}/{self.max_messages} messages, {ttl}s remaining")
                return False, error_msg, retry_after_seconds
            
            # Increment counter (TTL is preserved)
            await client.incr(key)
            remaining = self.max_messages - count - 1
            logger.debug(f"Rate limit check passed for session {session_id}: {count + 1}/{self.max_messages} messages, {remaining} remaining")
            return True, None, None
            
        except Exception as e:
            # If Redis fails, allow the request (fail open) but log the error
            logger.error(f"Rate limiter error for session {session_id}: {e}", exc_info=True)
            # Fail open - allow request if rate limiter fails
            return True, None, None
    
    async def get_rate_limit_status(self, session_id: str) -> dict:
        """
        Get current rate limit status for a session.
        
        Args:
            session_id: The session ID to check
            
        Returns:
            Dictionary with rate limit information
        """
        try:
            client = await self._get_client()
            key = f"rate_limit:session:{session_id}"
            
            current_count = await client.get(key)
            ttl = await client.ttl(key)
            
            if current_count is None:
                return {
                    "session_id": session_id,
                    "messages_used": 0,
                    "messages_remaining": self.max_messages,
                    "limit_reset_seconds": None,
                    "is_limited": False
                }
            
            count = int(current_count)
            remaining = max(0, self.max_messages - count)
            
            return {
                "session_id": session_id,
                "messages_used": count,
                "messages_remaining": remaining,
                "limit_reset_seconds": ttl if ttl > 0 else None,
                "is_limited": count >= self.max_messages
            }
        except Exception as e:
            logger.error(f"Error getting rate limit status for session {session_id}: {e}", exc_info=True)
            return {
                "session_id": session_id,
                "messages_used": 0,
                "messages_remaining": self.max_messages,
                "limit_reset_seconds": None,
                "is_limited": False,
                "error": str(e)
            }
    
    async def reset_rate_limit(self, session_id: str) -> bool:
        """
        Reset rate limit for a session (admin function).
        
        Args:
            session_id: The session ID to reset
            
        Returns:
            True if reset successful, False otherwise
        """
        try:
            client = await self._get_client()
            key = f"rate_limit:session:{session_id}"
            await client.delete(key)
            logger.info(f"Rate limit reset for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error resetting rate limit for session {session_id}: {e}", exc_info=True)
            return False
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None


# Singleton instance
rate_limiter = RateLimiter()

