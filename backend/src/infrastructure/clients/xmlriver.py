from __future__ import annotations
import httpx
import logging
from typing import List, Dict, Any, Mapping
from src.core.constants import APIEndpoints
from src.domain.exceptions import ExternalAPIException
from src.infrastructure.utils.parser import parse_xml_river_response

logger = logging.getLogger(__name__)

class XMLRiverClient:
    def __init__(self, user_id: str, api_key: str):
        self.user_id = user_id
        self.api_key = api_key
        self.base_url = APIEndpoints.XMLRIVER_YANDEX

    async def search(self, query: str, count: int = 50, region: int = 225) -> List[Dict[str, Any]]:
        params: Mapping[str, str | int] = {
            "user": self.user_id,
            "key": self.api_key,
            "query": query,
            "lr": region,
            "groupby": count
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                
                xml_content = response.text
                results = parse_xml_river_response(xml_content)
                
                if not results and "error" in xml_content.lower():
                    logger.warning(f"XMLRiver returned soft error: {xml_content}")
                    return [] # просто пустой список чтоб не падать
                    
                return results
                
        except httpx.HTTPError:
            logger.warning("Search request failed")
            return []
        except Exception as e:
            logger.exception("Search error")
            return []
