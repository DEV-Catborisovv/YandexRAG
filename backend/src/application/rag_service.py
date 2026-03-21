from __future__ import annotations
import asyncio
import logging
from typing import List, Dict, Any
from src.domain.models import SearchQuery, RAGResponse, SearchResult
from src.domain.services.chunker import Chunker
from src.domain.services.ranker import ChunkRanker
from src.domain.services.source_processor import SourceProcessor
from src.infrastructure.clients.xmlriver import XMLRiverClient
from src.infrastructure.clients.yandex_gpt import YandexGPTClient
from src.infrastructure.utils.scraper import scrape_page
from src.core.constants import DefaultConfigs
from src.core import prompts

# логгер
logger = logging.getLogger(__name__)


class RAGService:
    
    def __init__(
        self, 
        search_client: XMLRiverClient,
        ranker: ChunkRanker,
        generation_client: YandexGPTClient,
        chunker: Chunker,
        source_processor: SourceProcessor
    ) -> None:
        self.search_client = search_client
        self.ranker = ranker
        self.generation_client = generation_client
        self.chunker = chunker
        self.source_processor = source_processor


    async def ask(self, query_data: SearchQuery) -> RAGResponse:
        # рефрейзим запрос чтоб поиск был точнее
        rephrased_query = await self.generation_client.rephrase_query(
            query=query_data.query, 
            history=query_data.history
        )
        logger.info(f"search query: '{rephrased_query}'")

        # идем в поиск
        results = await self.search_client.search(rephrased_query)
        if not results:
            return RAGResponse(answer="Ничего не нашел, сорян.", sources=[])


        # скрапим страницы
        scrape_tasks = [
            scrape_page(results[i]['url']) 
            for i in range(min(query_data.scrape_top_n, len(results)))
        ]
        scraped_texts = await asyncio.gather(*scrape_tasks)

        all_chunks: List[SearchResult] = []
        for i, res in enumerate(results[:20]):
            content = scraped_texts[i] if i < len(scraped_texts) else None
            # если контент мелкий, берем сниппет из поиска
            full_text = content if content and len(content) > 200 else res['snippet']
            
            for passage in self.chunker.split(full_text):
                all_chunks.append(SearchResult(
                    snippet=passage,
                    url=res['url'],
                    title=res['title']
                ))


        # смотрим семантику и находим по чанкам (быстро)
        candidate_passages = await self.ranker.rank_chunks(
            query_data.query, 
            all_chunks, 
            top_k=20
        )

        # 2 llm-judge: просим гптшку оценить релевантность
        scoring_tasks = [
            self.generation_client.score_passage(query_data.query, p.snippet)
            for p in candidate_passages
        ]
        scores = await asyncio.gather(*scoring_tasks)

        doc_map: Dict[str, SearchResult] = {}
        for i, score in enumerate(scores):
            p = candidate_passages[i]
            # если оценка норм или яндекс упал (-1), берем
            if score >= DefaultConfigs.JUDGE_MIN_SCORE or score == -1:
                if p.url not in doc_map:
                    # ищем индекс шоб вытащить фулл текст
                    orig_res_idx = next((j for j, res in enumerate(results) if res['url'] == p.url), None)
                    if orig_res_idx is not None:
                        content = scraped_texts[orig_res_idx] if orig_res_idx < len(scraped_texts) else None
                        full_text = content if content and len(content) > 200 else results[orig_res_idx]['snippet']
                        
                        doc_map[p.url] = SearchResult(
                            title=p.title,
                            url=p.url,
                            snippet=full_text,
                            score=float(score)/10.0 if score != -1 else 0.5
                        )
        
        relevant_docs = list(doc_map.values())
        if not relevant_docs:
            if candidate_passages:
                # дефолтный фолбек
                relevant_docs = candidate_passages[:DefaultConfigs.TOP_K_CHUNKS]
            else:
                return RAGResponse(answer="Инфы мало, не могу ответить.", sources=[])

        # select glue вырезаем самые сочные куски из доков
        processing_tasks = [
            self.source_processor.process_document(query_data.query, doc)
            for doc in relevant_docs[:10]
        ]
        processed_docs = await asyncio.gather(*processing_tasks)

        # финальный выбор 5 победителей
        winners = await self.generation_client.select_winners(
            query=query_data.query, 
            candidates=processed_docs
        )

        winners = winners[:DefaultConfigs.TOP_K_CHUNKS]

        # формируем контекст
        context = self._format_context(winners)
        words = context.split()
        if len(words) > DefaultConfigs.MAX_TOTAL_TOKENS:
            context = " ".join(words[:DefaultConfigs.MAX_TOTAL_TOKENS]) + "..."


        # генерация ответа
        answer = await self.generation_client.generate_answer(
            prompt=f"User Question: {query_data.query}\n\nContext:\n{context}",
            system_prompt=prompts.NEYRO_SYSTEM
        )


        # верифай на галюны
        is_grounded, feedback = await self.generation_client.verify_answer(
            query=query_data.query,
            context=context,
            answer=answer
        )

        if not is_grounded:
            logger.warning(f"hallucination detected: {feedback}")
            # исправляем если надо
            answer = await self.generation_client.generate_answer(
                prompt=prompts.CORRECTION.format(
                    query=query_data.query,
                    context=context,
                    answer=answer,
                    feedback=feedback
                ),
                system_prompt=prompts.NEYRO_SYSTEM
            )

        return RAGResponse(answer=answer, sources=winners)


    def _format_context(self, sources: List[SearchResult]) -> str:
        # просто склеиваем сорсы в один текст
        formatted = []
        for i, s in enumerate(sources, 1):
            formatted.append(f"Source [{i}]: {s.title}\nURL: {s.url}\nText: {s.snippet}")
            
        return "\n---\n".join(formatted)
