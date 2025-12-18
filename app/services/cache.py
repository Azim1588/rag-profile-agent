"""
Redis-based caching service for query embeddings and retrieval results.
"""
import hashlib
import json
import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings
import os

logger = logging.getLogger(__name__)

# Use same Redis client pattern as redis_memory.py
try:
    import redis.asyncio as redis_async
    REDIS_ASYNC_AVAILABLE = True
except ImportError:
    REDIS_ASYNC_AVAILABLE = False
    logger.warning("redis.asyncio not available, cache operations will be synchronous")


class CacheService:
    """Service for caching query embeddings and retrieval results."""
    
    def __init__(self, host: str = None, port: int = None, db: int = None, ttl_seconds: int = 3600):
        self.redis_client: Optional[redis.Redis] = None
        self.ttl_seconds = ttl_seconds  # Default TTL: 1 hour
        
        # Detect Docker environment
        is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
        self.host = host or ('redis' if is_docker else settings.REDIS_HOST)
        self.port = port or settings.REDIS_PORT
        self.db = db or (settings.REDIS_DB + 3)  # Use DB 3 for cache (0=Celery, 1=results, 2=session)
    
    async def _get_client(self):
        """Get or create Redis client."""
        if self.redis_client is None:
            if REDIS_ASYNC_AVAILABLE:
                self.redis_client = redis_async.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=None,
                    decode_responses=False,  # Keep binary for embeddings
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
            else:
                # Fallback: synchronous client (not recommended but better than nothing)
                import redis as redis_sync
                self.redis_client = redis_sync.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    decode_responses=False,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
                logger.warning("Using synchronous Redis client for cache - operations may block")
        return self.redis_client
    
    def _hash_query(self, query: str) -> str:
        """Generate hash for query string."""
        return hashlib.sha256(query.encode()).hexdigest()
    
    async def get_embedding(self, query: str) -> Optional[List[float]]:
        """Get cached embedding for query."""
        try:
            client = await self._get_client()
            key = f"embedding:{self._hash_query(query)}"
            if REDIS_ASYNC_AVAILABLE:
                cached = await client.get(key)
            else:
                cached = client.get(key)  # Synchronous
            if cached:
                if isinstance(cached, bytes):
                    cached = cached.decode()
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache miss/error for embedding: {e}")
        return None
    
    async def set_embedding(self, query: str, embedding: List[float], ttl_seconds: int = None):
        """Cache embedding for query."""
        try:
            client = await self._get_client()
            key = f"embedding:{self._hash_query(query)}"
            ttl = ttl_seconds or self.ttl_seconds
            if REDIS_ASYNC_AVAILABLE:
                await client.setex(key, ttl, json.dumps(embedding))
            else:
                client.setex(key, ttl, json.dumps(embedding))  # Synchronous
        except Exception as e:
            logger.warning(f"Failed to cache embedding: {e}")
    
    async def get_retrieval_results(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached retrieval results for query."""
        try:
            client = await self._get_client()
            key = f"retrieval:{self._hash_query(query)}"
            if REDIS_ASYNC_AVAILABLE:
                cached = await client.get(key)
            else:
                cached = client.get(key)  # Synchronous
            if cached:
                if isinstance(cached, bytes):
                    cached = cached.decode()
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache miss/error for retrieval: {e}")
        return None
    
    async def set_retrieval_results(self, query: str, results: List[Dict[str, Any]], ttl_seconds: int = 300):
        """Cache retrieval results (shorter TTL since documents can change)."""
        try:
            client = await self._get_client()
            key = f"retrieval:{self._hash_query(query)}"
            # Shorter TTL for retrieval results (5 minutes)
            if REDIS_ASYNC_AVAILABLE:
                await client.setex(key, ttl_seconds, json.dumps(results))
            else:
                client.setex(key, ttl_seconds, json.dumps(results))  # Synchronous
        except Exception as e:
            logger.warning(f"Failed to cache retrieval results: {e}")
    
    async def invalidate_retrieval_cache(self):
        """Invalidate all retrieval caches (call after document updates)."""
        try:
            client = await self._get_client()
            # Delete all keys matching pattern (use SCAN for safety)
            pattern = "retrieval:*"
            if REDIS_ASYNC_AVAILABLE:
                async for key in client.scan_iter(match=pattern):
                    await client.delete(key)
            else:
                # Synchronous fallback
                for key in client.scan_iter(match=pattern):
                    client.delete(key)
        except Exception as e:
            logger.warning(f"Failed to invalidate retrieval cache: {e}")
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client and REDIS_ASYNC_AVAILABLE:
            await self.redis_client.close()
            self.redis_client = None


# Global cache service instance
cache_service = CacheService()

