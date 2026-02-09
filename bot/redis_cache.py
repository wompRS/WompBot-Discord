"""
Redis Cache Utility
Provides in-memory caching for frequently accessed data to reduce database load.
Falls back gracefully if Redis is unavailable.
"""

import os
import json
from typing import Any, Optional
from datetime import timedelta


class RedisCache:
    """Redis-based caching with graceful fallback"""

    def __init__(self):
        """Initialize Redis connection"""
        self._client = None
        self._enabled = False
        self._connect()

    def _connect(self):
        """Attempt to connect to Redis"""
        redis_host = os.getenv('REDIS_HOST')
        redis_port = int(os.getenv('REDIS_PORT', '6379'))

        if not redis_host:
            print("ℹ️  Redis not configured (REDIS_HOST not set) - caching disabled")
            return

        try:
            import redis
            redis_password = os.getenv('REDIS_PASSWORD')
            self._client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self._client.ping()
            self._enabled = True
            print(f"✅ Redis cache connected ({redis_host}:{redis_port})")
        except ImportError:
            print("⚠️  redis package not installed - caching disabled")
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e} - caching disabled")

    @property
    def enabled(self) -> bool:
        """Check if Redis caching is available"""
        return self._enabled

    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/error
        """
        if not self._enabled:
            return None

        try:
            value = self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"⚠️  Redis get error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """
        Set a value in cache

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time-to-live in seconds (default 5 minutes)

        Returns:
            True if successful
        """
        if not self._enabled:
            return False

        try:
            self._client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            print(f"⚠️  Redis set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete a key from cache

        Args:
            key: Cache key

        Returns:
            True if successful
        """
        if not self._enabled:
            return False

        try:
            self._client.delete(key)
            return True
        except Exception as e:
            print(f"⚠️  Redis delete error: {e}")
            return False

    def get_or_set(self, key: str, fallback_fn, ttl: int = 300) -> Any:
        """
        Get from cache, or compute and cache if missing

        Args:
            key: Cache key
            fallback_fn: Function to call if cache miss (must return JSON-serializable value)
            ttl: Time-to-live in seconds

        Returns:
            Cached or computed value
        """
        # Try cache first
        cached = self.get(key)
        if cached is not None:
            return cached

        # Cache miss - compute value
        value = fallback_fn()

        # Cache the result
        if value is not None:
            self.set(key, value, ttl)

        return value

    async def get_or_set_async(self, key: str, fallback_fn, ttl: int = 300) -> Any:
        """
        Async version of get_or_set

        Args:
            key: Cache key
            fallback_fn: Async function to call if cache miss
            ttl: Time-to-live in seconds

        Returns:
            Cached or computed value
        """
        # Try cache first
        cached = self.get(key)
        if cached is not None:
            return cached

        # Cache miss - compute value
        value = await fallback_fn()

        # Cache the result
        if value is not None:
            self.set(key, value, ttl)

        return value

    def increment(self, key: str, amount: int = 1, ttl: int = 3600) -> int:
        """
        Increment a counter in cache (useful for rate limiting)

        Args:
            key: Cache key
            amount: Amount to increment by
            ttl: Time-to-live in seconds (sets on first increment)

        Returns:
            New counter value, or 0 if error/disabled
        """
        if not self._enabled:
            return 0

        try:
            pipe = self._client.pipeline()
            pipe.incr(key, amount)
            pipe.expire(key, ttl)
            results = pipe.execute()
            return results[0]
        except Exception as e:
            print(f"⚠️  Redis increment error: {e}")
            return 0

    def get_counter(self, key: str) -> int:
        """
        Get current counter value

        Args:
            key: Cache key

        Returns:
            Counter value, or 0 if not found/error
        """
        if not self._enabled:
            return 0

        try:
            value = self._client.get(key)
            return int(value) if value else 0
        except Exception as e:
            print(f"⚠️  Redis get_counter error: {e}")
            return 0

    # Convenience methods for common cache keys

    def cache_user_facts(self, user_id: int, guild_id: int, facts: list, ttl: int = 600):
        """Cache user facts for 10 minutes by default"""
        key = f"user_facts:{guild_id}:{user_id}"
        return self.set(key, facts, ttl)

    def get_user_facts(self, user_id: int, guild_id: int) -> Optional[list]:
        """Get cached user facts"""
        key = f"user_facts:{guild_id}:{user_id}"
        return self.get(key)

    def cache_recent_messages(self, channel_id: int, messages: list, ttl: int = 60):
        """Cache recent messages for 1 minute by default"""
        key = f"recent_msgs:{channel_id}"
        return self.set(key, messages, ttl)

    def get_recent_messages(self, channel_id: int) -> Optional[list]:
        """Get cached recent messages"""
        key = f"recent_msgs:{channel_id}"
        return self.get(key)

    def invalidate_recent_messages(self, channel_id: int):
        """Invalidate cached messages when new message arrives"""
        key = f"recent_msgs:{channel_id}"
        return self.delete(key)

    def check_rate_limit(self, user_id: int, action: str, limit: int, window: int) -> tuple[bool, int]:
        """
        Check and increment rate limit counter

        Args:
            user_id: User ID
            action: Action type (e.g., 'message', 'search', 'factcheck')
            limit: Maximum allowed in window
            window: Time window in seconds

        Returns:
            (allowed: bool, current_count: int)
        """
        key = f"ratelimit:{action}:{user_id}"
        current = self.increment(key, 1, window)
        return (current <= limit, current)

    def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self._enabled:
            return {'enabled': False}

        try:
            info = self._client.info('memory')
            return {
                'enabled': True,
                'used_memory': info.get('used_memory_human', 'unknown'),
                'max_memory': info.get('maxmemory_human', 'unknown'),
                'keys': self._client.dbsize()
            }
        except Exception as e:
            return {'enabled': True, 'error': str(e)}


# Global instance (lazy-loaded)
_cache_instance = None


def get_cache() -> RedisCache:
    """Get the global cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance
