from __future__ import annotations
import logging
import numpy as np
from typing import List, Dict, Any
from src.infrastructure.clients.embeddings import YandexEmbeddingsClient
from src.domain.models import SearchResult

logger = logging.getLogger(__name__)

class ChunkRanker:
    def __init__(self, embedding_client: YandexEmbeddingsClient) -> None:
        self.embedding_client = embedding_client

    async def rank_chunks(
        self, 
        query: str, 
        chunks: List[SearchResult], 
        top_k: int = 10
    ) -> List[SearchResult]:
        if not chunks:
            return []

        logger.info(f"Re-ranking {len(chunks)} chunks for query: {query}")
        
        query_emb = await self.embedding_client.get_query_embedding(query)
        if not query_emb:
            return chunks[:top_k]

        texts = [c.snippet for c in chunks]
        chunk_embs = await self.embedding_client.get_embeddings(texts)
        
        if not chunk_embs or len(chunk_embs) != len(chunks):
            return chunks[:top_k]

        query_vec = np.array(query_emb).flatten()
        norm_q = np.linalg.norm(query_vec)
        
        scored_results: List[tuple[float, SearchResult]] = []
        for i, c_emb in enumerate(chunk_embs):
            c_vec = np.array(c_emb).flatten()
            norm_c = np.linalg.norm(c_vec)
            
            sim = 0.0
            if norm_q > 0 and norm_c > 0:
                sim = float(np.dot(query_vec, c_vec) / (norm_q * norm_c))
            
            old_c = chunks[i]
            scored_results.append((sim, SearchResult(
                title=old_c.title,
                url=old_c.url,
                snippet=old_c.snippet,
                score=sim
            )))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [r for sim, r in scored_results[:top_k]]
