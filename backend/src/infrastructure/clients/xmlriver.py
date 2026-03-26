from __future__ import annotations
import httpx
import logging
from typing import List, Dict, Any, Mapping
from src.core.constants import APIEndpoints
from src.domain.exceptions import ExternalAPIException
from src.infrastructure.utils.parser import parse_xml_river_response

logger = logging.getLogger(__name__)

from src.infrastructure.clients.cache import cache

class XMLRiverClient:
    def __init__(self, user_id: str, api_key: str):
        self.user_id = user_id
        self.api_key = api_key
        self.base_url = APIEndpoints.XMLRIVER_YANDEX

    async def search(self, query: str, count: int = 50, region: int = 225) -> List[Dict[str, Any]]:
        # Check cache first
        cache_key = f"{query}:{region}:{count}"
        results = cache.get("search", cache_key)
        
        if not results:
            params: Mapping[str, str | int] = {
                "user": self.user_id,
                "key": self.api_key,
                "query": query,
                "lr": region,
                "groupby": count
            }
            
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.get(self.base_url, params=params)
                        response.raise_for_status()
                        
                        xml_content = response.text
                        results = parse_xml_river_response(xml_content)
                        
                        if not results and "error" in xml_content.lower():
                            if "500" in xml_content or "перезапрос" in xml_content:
                                wait_time = 1.0 * (attempt + 1)
                                logger.warning(f"XMLRiver 500 (attempt {attempt+1}): {xml_content}. Retrying in {wait_time}s...")
                                import asyncio
                                await asyncio.sleep(wait_time)
                                continue
                        
                        # Store in cache for 24 hours
                        if results:
                            cache.set("search", cache_key, results, ttl=86400)
                        break
                        
                except httpx.HTTPError:
                    logger.warning(f"Search request failed (attempt {attempt+1})")
                    import asyncio
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.exception("Search error")
                    return []
        else:
            logger.info(f"Using cached search results for query: {query}")

        if not results:
            return []

        # Фильтрация нетекстовых результатов (картинки, стоки и т.д.)
        EXCLUDED_PATTERNS = [
            "yandex.ru/images", "google.com/images", "bing.com/images", 
            "google.com/search?tbm=isch", "shutterstock.com", "istockphoto.com",
            "ru.depositphotos.com", "dreamstime.com", "123rf.com", "pinterest.com"
        ]
        
        filtered_results = []
        for res in results:
            url_lower = res['url'].lower()
            if not any(pattern in url_lower for pattern in EXCLUDED_PATTERNS):
                filtered_results.append(res)
        
        return filtered_results
