import asyncio
import logging
import random
from typing import Callable, Any, TypeVar, Coroutine

logger = logging.getLogger(__name__)

T = TypeVar("T")

class RateLimiter:
    """Глобальный лимитер запросов для Yandex Cloud."""
    _instance = None
    _semaphore = asyncio.Semaphore(4)  # Новый ключ - возвращаемся к 4 параллельным запросам

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RateLimiter, cls).__new__(cls)
        return cls._instance

    @classmethod
    async def run(cls, coro: Coroutine[Any, Any, T], max_retries: int = 5) -> T:
        for attempt in range(max_retries):
            async with cls._semaphore:
                try:
                    return await coro
                except Exception as e:
                    err_str = str(e)
                    if any(x in err_str for x in ["RESOURCE_EXHAUSTED", "rate limit exceed", "PERMISSION_DENIED", "StatusCode.PERMISSION_DENIED"]):
                        wait_time = (3 * (attempt + 1)) + random.uniform(1, 3)  # Быстрый backoff: 4-9s, 7-12s, 10-15s
                        logger.warning(f"Yandex Rate Guard. Waiting {wait_time:.2f}s... (Attempt {attempt+1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    raise e
        
        raise Exception("Yandex Cloud Rate Limit exceeded after all retries.")
import threading
import time

class SyncRateLimiter:
    """Синхронная версия лимитера для работы в многопоточном DSPy."""
    _lock = threading.Lock()
    _semaphore = threading.Semaphore(4)

    @classmethod
    def run(cls, func: Callable[..., T], *args, **kwargs) -> T:
        max_retries = 5
        for attempt in range(max_retries):
            with cls._semaphore:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    err_str = str(e)
                    if any(x in err_str for x in ["RESOURCE_EXHAUSTED", "rate limit exceed", "PERMISSION_DENIED", "StatusCode.PERMISSION_DENIED"]):
                        wait_time = (3 * (attempt + 1)) + random.uniform(1, 3)
                        logger.warning(f"Yandex Rate Guard (Sync). Waiting {wait_time:.2f}s... (Attempt {attempt+1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    raise e
        raise Exception("Yandex Cloud Rate Limit exceeded (Sync)")
