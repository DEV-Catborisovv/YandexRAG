from __future__ import annotations
import asyncio
import logging
from typing import List, Any
from yandex_cloud_ml_sdk import YCloudML
from src.infrastructure.clients.limiter import RateLimiter
from src.domain.exceptions import ExternalAPIException
from src.core.constants import YandexModelNames

logger = logging.getLogger(__name__)

class YandexEmbeddingsClient:
    def __init__(self, folder_id: str, api_key: str):
        self.folder_id = folder_id
        self.api_key = api_key
        self.sdk = YCloudML(folder_id=folder_id, auth=api_key)

    async def get_embeddings(self, texts: List[str], model_type: str = YandexModelNames.EMBEDDING_DOC.value) -> List[List[float]]:
        if not texts:
            return []

        try:
            model = self.sdk.models.text_embeddings(model_type)
            loop = asyncio.get_running_loop()
            
            embeddings: List[List[float]] = []
            for text in texts:
                if not text.strip():
                    embeddings.append([0.0] * 256)
                    continue
                
                # Defensive truncation: Yandex Embeddings limit is 2048 tokens
                # 500 words OR 2000 chars is a very safe limit.
                safe_text = " ".join(text.split()[:500])[:2000]
                
                try:
                    # Run with rate limiting
                    loop = asyncio.get_running_loop()
                    result = await RateLimiter.run(loop.run_in_executor(None, lambda: model.run(safe_text)))
                    
                    emb: List[float] = []
                    if hasattr(result, "embedding"):
                        raw_emb = getattr(result, "embedding")
                        if isinstance(raw_emb, (list, tuple)):
                            emb = [float(x) for x in raw_emb]
                    
                    if not emb:
                        logger.warning(f"Could not extract embedding for text: {text[:50]}...")
                        emb = [0.0] * 256
                    embeddings.append(emb)
                except Exception as e:
                    logger.warning(f"Single embedding failed: {e}")
                    embeddings.append([0.0] * 256)
                
            return embeddings
                
            return embeddings
            
        except Exception as e:
            logger.exception("Yandex Embeddings generation failed")
            raise ExternalAPIException("YandexEmbeddings", 500, str(e))

    async def get_query_embedding(self, query: str) -> List[float]:
        """Convenience method for query embeddings."""
        embs = await self.get_embeddings([query], model_type=YandexModelNames.EMBEDDING_QUERY.value)
        return embs[0] if embs else []
