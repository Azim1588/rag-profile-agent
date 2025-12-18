"""Redis-based session memory service for short-term conversation memory."""
import json
from typing import List, Optional, Dict, Any
from datetime import timedelta
try:
    import redis.asyncio as redis
except ImportError:
    # Fallback for older redis versions
    import redis
    # Will need to use sync redis if async not available
from app.core.config import settings


class RedisMemoryService:
    """Service for managing short-term session memory in Redis."""
    
    def __init__(self):
        """Initialize Redis connection."""
        self.redis_client: Optional[redis.Redis] = None
        self._connection_pool = None
    
    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self.redis_client is None:
            # In Docker, use service name; otherwise use host from settings
            import os
            # Check if we're in Docker (common indicator)
            is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
            
            if is_docker:
                # In Docker, use service name 'redis' instead of 'localhost'
                host = 'redis'  # Docker service name
            else:
                host = settings.REDIS_HOST
            
            port = settings.REDIS_PORT
            db = settings.REDIS_DB + 2  # Use DB 2 for session memory (0 for Celery, 1 for results)
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
    
    async def add_to_session(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: int = 3600  # Default 1 hour TTL
    ) -> None:
        """Add a message to session memory."""
        client = await self._get_client()
        key = f"session:{session_id}:messages"
        
        message = {
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": self._get_timestamp()
        }
        
        # Add to list (left push to maintain order)
        await client.lpush(key, json.dumps(message))
        
        # Set TTL on the key
        await client.expire(key, ttl_seconds)
        
        # Trim list to last N messages (keep last 50 messages per session)
        await client.ltrim(key, 0, 49)
    
    async def get_session_memory(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent messages from session memory."""
        client = await self._get_client()
        key = f"session:{session_id}:messages"
        
        try:
            # Get last N messages (rightmost in list)
            messages_json = await client.lrange(key, 0, limit - 1)
            messages = [json.loads(msg) for msg in reversed(messages_json)]
            return messages
        except Exception as e:
            print(f"Error getting session memory: {e}")
            return []
    
    async def clear_session(self, session_id: str) -> None:
        """Clear all messages for a session."""
        client = await self._get_client()
        key = f"session:{session_id}:messages"
        await client.delete(key)
    
    async def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get summary information about a session."""
        client = await self._get_client()
        key = f"session:{session_id}:messages"
        
        try:
            message_count = await client.llen(key)
            ttl = await client.ttl(key)
            
            return {
                "session_id": session_id,
                "message_count": message_count,
                "ttl_seconds": ttl
            }
        except Exception as e:
            print(f"Error getting session summary: {e}")
            return None
    
    def _get_timestamp(self) -> float:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().timestamp()
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None


# Singleton instance
redis_memory_service = RedisMemoryService()

