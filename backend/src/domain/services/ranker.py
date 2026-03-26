from __future__ import annotations
import logging
import numpy as np
import asyncio
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from src.infrastructure.clients.embeddings import YandexEmbeddingsClient
from src.domain.models import SearchResult
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

class BM25Ranker:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def rank_chunks(self, query: str, chunks: List[SearchResult], top_k: int = 10) -> List[SearchResult]:
        if not chunks:
            return []
        
        # Tokenization (Russian-friendly splitting)
        def tokenize(text: str) -> List[str]:
            return text.lower().replace('.', ' ').replace(',', ' ').split()

        corpus = [tokenize(c.snippet) for c in chunks]
        bm25 = BM25Okapi(corpus, k1=self.k1, b=self.b)
        
        tokenized_query = tokenize(query)
        scores = bm25.get_scores(tokenized_query)
        
        # Min-Max Normalization to [0, 1]
        if len(scores) > 0 and (max(scores) - min(scores)) > 0:
            scores = (scores - min(scores)) / (max(scores) - min(scores))
        
        scored_results = []
        for i, score in enumerate(scores):
            chunks[i].score = float(score)
            scored_results.append(chunks[i])
            
        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:top_k]

class CrossEncoderRanker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model_name = model_name
        self._model: Optional[CrossEncoder] = None

    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading Cross-Encoder model: {self.model_name}")
            try:
                self._model = CrossEncoder(self.model_name, max_length=512)
            except Exception as e:
                logger.error(f"Failed to load Cross-Encoder: {e}")
                return None
        return self._model

    async def rank_chunks(self, query: str, chunks: List[SearchResult], top_k: int = 5) -> List[SearchResult]:
        model = self.model
        if not model or not chunks:
            return chunks[:top_k]

        pairs = [[query, c.snippet] for c in chunks]
        
        # Run in executor to avoid blocking event loop
        loop = asyncio.get_running_loop()
        scores = await loop.run_in_executor(None, lambda: model.predict(pairs))
        
        scored_results = []
        for i, score in enumerate(scores):
            chunks[i].score = float(score)
            scored_results.append(chunks[i])
            
        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:top_k]

class ChunkRanker:
    """Hybrid Ranker combining Vector (Embeddings) and BM25, with an optional Cross-Encoder stage."""
    def __init__(
        self, 
        embedding_client: YandexEmbeddingsClient,
        cross_encoder: Optional[CrossEncoderRanker] = None
    ) -> None:
        self.embedding_client = embedding_client
        self.bm25 = BM25Ranker()
        self.cross_encoder = cross_encoder or CrossEncoderRanker()

    async def _get_vector_scores(self, query: str, chunks: List[SearchResult]) -> np.ndarray:
        query_emb = await self.embedding_client.get_query_embedding(query)
        if not query_emb:
            return np.zeros(len(chunks))

        texts = [c.snippet for c in chunks]
        chunk_embs = await self.embedding_client.get_embeddings(texts)
        
        if not chunk_embs or len(chunk_embs) != len(chunks):
            return np.zeros(len(chunks))

        query_vec = np.array(query_emb).flatten()
        norm_q = np.linalg.norm(query_vec)
        
        scores = []
        for c_emb in chunk_embs:
            c_vec = np.array(c_emb).flatten()
            norm_c = np.linalg.norm(c_vec)
            sim = 0.0
            if norm_q > 0 and norm_c > 0:
                sim = float(np.dot(query_vec, c_vec) / (norm_q * norm_c))
            scores.append(sim)
        
        return np.array(scores)

    async def rank_chunks(
        self, 
        query: str, 
        chunks: List[SearchResult], 
        top_k: int = 10,
        use_reranker: bool = True
    ) -> List[SearchResult]:
        if not chunks:
            return []

        logger.info(f"Hybrid Re-ranking {len(chunks)} chunks for query: {query}")
        
        # 1. Vector Scores
        vector_scores = await self._get_vector_scores(query, chunks)
        
        # 2. BM25 Scores
        # Tokenization (Russian-friendly splitting)
        def tokenize(text: str) -> List[str]:
            return text.lower().replace('.', ' ').replace(',', ' ').split()

        corpus = [tokenize(c.snippet) for c in chunks]
        bm25_obj = BM25Okapi(corpus)
        bm25_scores = np.array(bm25_obj.get_scores(tokenize(query)))
        
        # Normalize BM25
        if len(bm25_scores) > 0 and (max(bm25_scores) - min(bm25_scores)) > 0:
            bm25_scores = (bm25_scores - min(bm25_scores)) / (max(bm25_scores) - min(bm25_scores))
        else:
            bm25_scores = np.zeros(len(chunks))

        # 3. Hybrid Combination (Weighted Average)
        # 0.7 Vector + 0.3 BM25 is a good default
        hybrid_scores = 0.7 * vector_scores + 0.3 * bm25_scores
        
        # 4. Domain Boosting and Diversity
        TRUSTED_DOMAINS = {
            "wikipedia.org", "2gis.ru", "afisha.ru", "maps.yandex.ru", 
            "dzen.ru", "rbc.ru", "habr.com", "kp.ru", "tass.ru", "gorpom.ru",
            "kudago.com", "kassir.ru", "vokrugsveta.ru"
        }
        
        scored_results: List[SearchResult] = []
        domain_counts: Dict[str, int] = {}
        
        for i, score in enumerate(hybrid_scores):
            c = chunks[i]
            final_score = float(score)
            
            # Domain Boost (+0.2 for trusted sources to align with Yandex)
            domain = c.url.split('//')[-1].split('/')[0].replace('www.', '')
            if any(td in domain for td in TRUSTED_DOMAINS):
                final_score += 0.2
            
            # Diversity Penalty (-0.1 for each subsequent result from the same domain)
            base_domain = '.'.join(domain.split('.')[-2:])
            count = domain_counts.get(base_domain, 0)
            if count > 0:
                final_score -= 0.1 * count
            domain_counts[base_domain] = count + 1
            
            scored_results.append(SearchResult(
                title=c.title,
                url=c.url,
                snippet=c.snippet,
                score=final_score,
                metadata=c.metadata
            ))

        scored_results.sort(key=lambda x: x.score, reverse=True)
        top_pool = scored_results[:top_k * 2] # Take a larger pool for reranking

        # 5. Cross-Encoder Reranking (Stage 2)
        if use_reranker:
            final_winners = await self.cross_encoder.rank_chunks(query, top_pool, top_k=top_k)
            return final_winners
        
        return top_pool[:top_k]
