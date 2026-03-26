import json
import logging
import hashlib
from typing import Optional, Any
import redis
from src.config import Config

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, password: Optional[str] = None):
        try:
            self.client = redis.Redis(
                host=host, 
                port=port, 
                db=db, 
                password=password, 
                decode_responses=True,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self.client.ping()
            logger.info(f"Connected to Redis at {host}:{port}")
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}. Caching will be disabled.")
            self.client = None

    def _get_key(self, prefix: str, data: str) -> str:
        hash_val = hashlib.md5(data.encode()).hexdigest()
        return f"{prefix}:{hash_val}"

    def get(self, prefix: str, key_data: str) -> Optional[Any]:
        if not self.client:
            return None
        
        key = self._get_key(prefix, key_data)
        try:
            cached = self.client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
        return None

    def set(self, prefix: str, key_data: str, value: Any, ttl: int = 86400):
        if not self.client:
            return
        
        key = self._get_key(prefix, key_data)
        try:
            self.client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        except Exception as e:
            logger.warning(f"Redis set error: {e}")

# Global cache instance
import os
cache = RedisCache(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379))
)
