import logging
from typing import List, Dict, Tuple
from src.domain.models import SearchResult
from src.domain.services.chunker import Chunker
from src.domain.services.ranker import ChunkRanker
from src.core.constants import DefaultConfigs

# селект энд глю логика тута

logger = logging.getLogger(__name__)

class SourceProcessor:
    def __init__(
        self, 
        chunker: Chunker, 
        ranker: ChunkRanker,
        max_tokens: int = DefaultConfigs.MAX_TOKENS_PER_DOC
    ) -> None:
        self.chunker = chunker
        self.ranker = ranker
        self.max_tokens = max_tokens


    async def process_document(self, query: str, document: SearchResult) -> SearchResult:
        # если текста нет, ниче не делаем
        if not document.snippet:
            return document
            
        words_count = len(document.snippet.split())
        # если документ и так мелкий, сразу возвращаем (до 500 слов)
        if words_count <= 500:
            return document

        # 1. нарезаем на чанки
        chunks = self.chunker.split(document.snippet)
        
        # 2. скорим каждый чанк
        candidate_chunks = [
            SearchResult(
                title=document.title, 
                url=document.url, 
                snippet=chunk,
                metadata=document.metadata
            ) for chunk in chunks
        ]
        
        ranked_chunks = await self.ranker.rank_chunks(query, candidate_chunks)
        
        # 3. выбираем лучшие фрагменты пока не упремся в лимит
        indexed_chunks = []
        for i, chunk in enumerate(chunks):
            # ищем оценку чанка
            score = next((rc.score for rc in ranked_chunks if rc.snippet == chunk), 0.0)
            indexed_chunks.append({"index": i, "text": chunk, "score": score})
        
        # по убыванию скора
        sorted_chunks = sorted(indexed_chunks, key=lambda x: x["score"], reverse=True)
        
        selected_indices = []
        current_tokens = 0
        
        for chunk in sorted_chunks:
            chunk_tokens = len(chunk["text"].split())
            if current_tokens + chunk_tokens <= self.max_tokens:
                selected_indices.append(chunk["index"])
                current_tokens += chunk_tokens
            if current_tokens >= self.max_tokens:
                break
                
        if not selected_indices:
            # если вдруг пусто, берем первый кусок
            return SearchResult(
                title=document.title,
                url=document.url,
                snippet=chunks[0],
                score=document.score
            )


        # 4. склеиваем обратно по порядку (glue)
        selected_indices.sort()
        glued_text = "... ".join([chunks[i] for i in selected_indices])
        
        return SearchResult(
            title=document.title,
            url=document.url,
            snippet=glued_text,
            score=document.score 
        )
