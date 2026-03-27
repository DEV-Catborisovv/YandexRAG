from __future__ import annotations
import asyncio
import logging
from typing import List, Dict, Any
from src.domain.models import SearchQuery, RAGResponse, SearchResult
from src.domain.services.chunker import Chunker
from src.domain.services.ranker import ChunkRanker
from src.domain.services.source_processor import SourceProcessor
from src.domain.services.metrics import MetricService
from src.infrastructure.clients.xmlriver import XMLRiverClient
from src.infrastructure.clients.yandex_gpt import YandexGPTClient
from src.domain.services.geo_service import GeoService
from src.infrastructure.utils.scraper import scrape_page
from src.core.constants import DefaultConfigs
from src.core import prompts
import os
import json
import re

# логгер
logger = logging.getLogger(__name__)

# Путь к оптимизированным промптам (из DSPy)
PROMPTS_PROD_PATH = "config/prompts_prod.json"

class RAGService:
    def __init__(
        self, 
        search_client: XMLRiverClient,
        ranker: ChunkRanker,
        generation_client: YandexGPTClient,
        chunker: Chunker,
        source_processor: SourceProcessor,
        metric_service: MetricService = None,
        opt_winner_selector: Any = None,
        geo_service: GeoService = None
    ) -> None:
        self.search_client = search_client
        self.ranker = ranker
        self.generation_client = generation_client
        self.chunker = chunker
        self.source_processor = source_processor
        self.metric_service = metric_service or MetricService()
        self.opt_winner_selector = opt_winner_selector
        self.geo_service = geo_service

        # Load optimized chunking configuration if exists
        self._load_rag_config()

    def _load_rag_config(self):
        config_path = "config/rag_config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if "chunk_size" in config:
                        self.chunker.chunk_size = config["chunk_size"]
                    if "chunk_overlap" in config:
                        self.chunker.overlap = config["chunk_overlap"]
                logger.info(f"RAGService: Loaded optimized config from {config_path}")
            except Exception as e:
                logger.warning(f"RAGService: Failed to load config from {config_path}: {e}")


    async def ask(self, query_data: SearchQuery) -> RAGResponse:
        # 1. Standard retrieval and generation
        response = await self._ask_internal(query_data)
        
        # 2. Multi-Stage Verification
        context = self._format_context(response.sources)
        is_grounded, feedback = await self.generation_client.verify_answer(
            query=query_data.query,
            context=context,
            answer=response.answer
        )

        if not is_grounded:
            logger.info(f"Verification failed: {feedback}. Triggering sub-search.")
            # Извлекаем уточняющий запрос
            sub_query_text = await self.generation_client.generate_answer(
                prompts.VERIFICATION_QUERY_EXTRACTION.format(
                    query=query_data.query,
                    feedback=feedback
                )
            )
            logger.info(f"Sub-search query: {sub_query_text}")
            
            # Дополнительный поиск
            extra_results = await self.search_client.search(sub_query_text)
            if extra_results:
                # Скрапим новые источники
                extra_scrape_tasks = [scrape_page(r['url']) for r in extra_results[:3]]
                extra_scraped = await asyncio.gather(*extra_scrape_tasks)
                
                extra_chunks = []
                for i, r in enumerate(extra_results[:3]):
                    content, meta = extra_scraped[i]
                    full_text = content if content and len(content) > 200 else r['snippet']
                    for passage in self.chunker.split(full_text):
                        extra_chunks.append(SearchResult(
                            snippet=passage, url=r['url'], title=r['title'], metadata=meta
                        ))
                
                # Ранжируем новые чанки
                new_winners = await self.ranker.rank_chunks(sub_query_text, extra_chunks, top_k=3)
                # Добавляем к старым победителям
                all_winners = response.sources + new_winners
                response.sources = all_winners[:DefaultConfigs.TOP_K_CHUNKS]
                
                # Перегенерируем ответ с расширенным контекстом
                context = self._format_context(response.sources)
                system_prompt = prompts.ALICE_SYSTEM if query_data.mode == "alice" else prompts.NEYRO_SYSTEM

                response.answer = await self.generation_client.generate_answer(
                    prompt=f"User Question: {query_data.query}\n\nContext:\n{context}",
                    system_prompt=system_prompt
                )

        # 4. Логируем метрики
        self._log_metrics_if_gold(query_data.query, response.sources)
        return response

    async def stream_ask(self, query_data: SearchQuery):
        """Streaming version of the RAG flow."""
        
        async def status_cb(msg: str):
            # We must yield from the outer generator, so we use a trick or a queue?
            # Or just let _retrieve accept the queue. 
            # Simplified: we use a queue to pass statuses back to the generator.
            await status_queue.put(msg)

        status_queue = asyncio.Queue()
        
        # 1. Start retrieval in a background task
        async def run_retrieval():
            try:
                winners = await self._retrieve(query_data, status_callback=status_cb)
                await status_queue.put(winners) # Pass the final result through the queue
            except Exception as e:
                logger.exception(f"Retrieval failed in stream_ask: {e}")
                await status_queue.put([])

        retrieval_task = asyncio.create_task(run_retrieval())

        # 2. Yield statuses as they come
        winners = []
        while True:
            item = await status_queue.get()
            if isinstance(item, list):
                winners = item
                break
            yield json.dumps({"type": "status", "data": item}, ensure_ascii=False) + "\n"

        if not winners:
            yield json.dumps({"type": "token", "data": "Ничего не нашел по вашему запросу."}, ensure_ascii=False) + "\n"
            return

        yield json.dumps({"type": "status", "data": "Генерация ответа..."}, ensure_ascii=False) + "\n"
        context = self._format_context(winners)
        
        system_prompt = prompts.ALICE_SYSTEM if query_data.mode == "alice" else prompts.NEYRO_SYSTEM

        # Yield sources
        yield json.dumps({"type": "sources", "data": [s.model_dump() for s in winners]}, ensure_ascii=False) + "\n"
        
        # 2. Stream the answer
        async for chunk in self.generation_client.generate_answer_stream(
            prompt=f"User Question: {query_data.query}\n\nContext:\n{context}",
            system_prompt=system_prompt
        ):
            if chunk:
                yield json.dumps({"type": "token", "data": chunk}, ensure_ascii=False) + "\n"

    def _load_prod_prompts(self) -> Dict[str, str]:
        if os.path.exists(PROMPTS_PROD_PATH):
            try:
                with open(PROMPTS_PROD_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    async def _retrieve(self, query_data: SearchQuery, status_callback=None) -> List[SearchResult]:
        if status_callback:
            await status_callback("Генерация уточняющих запросов...")
            
        # 0. Извлекаем регион
        region_code = 225
        if self.geo_service:
            region_code = await self.geo_service.extract_region_code(query_data.query)
            logger.info(f"RAGService: Using region code {region_code} for query '{query_data.query}'")

        # 1. Генерируем под-запросы
        relevant_history = []
        for h in query_data.history[-5:]:
            if isinstance(h, dict) and 'role' in h and 'content' in h:
                relevant_history.append(f"{h['role']}: {h['content']}")
        history_str = "\n".join(relevant_history)
        
        try:
            mq_res = await self.generation_client.generate_answer(
                prompts.MULTI_QUERY_GENERATION.format(query=query_data.query, history=history_str)
            )
            search_queries = re.findall(r'\d+\.\s*(.+)', mq_res)
            if not search_queries:
                search_queries = [query_data.query]
            logger.info(f"generated sub-queries: {search_queries}")
        except Exception as e:
            logger.warning(f"Multi-query generation failed: {e}")
            search_queries = [query_data.query]

        if status_callback:
            await status_callback(f"Поиск в Яндекс ({len(search_queries)} запроса)...")
            
        # идем в поиск параллельно
        search_tasks = [self.search_client.search(q, region=region_code) for q in search_queries]
        search_results_list = await asyncio.gather(*search_tasks)
        
        # объединяем и дедуплицируем по URL
        YANDEX_TRUSTED_DOMAINS = [
            "wikipedia.org", "dzen.ru", "rbc.ru", "aif.ru", "calend.ru", 
            "securitylab.ru", "ruwiki.ru", "vokrugsveta.ru", "kp.ru", 
            "rt.com", "naukatv.ru", "mail.ru", "cyberleninka.ru", 
            "tass.ru", "habr.com", "yandex.ru", "5-tv.ru",
            "tproger.ru", "sber.ru", "vc.ru", "ixbt.com", "pikabu.ru", 
            "dtf.ru", "vedomosti.ru", "kommersant.ru", "forbes.ru"
        ]
        
        EXCLUDED_PATTERNS = ["/images", "tbm=isch", "pinterest.com", "shutterstock.com", "istockphoto.com"]

        all_results = []
        seen_urls = set()
        for results in search_results_list:
            if results:
                for res in results:
                    url = res['url']
                    url_lower = url.lower()
                    if url not in seen_urls and not any(p in url_lower for p in EXCLUDED_PATTERNS):
                        is_ru = any(url.endswith(suffix) for suffix in ['.ru', '.рф', '.su'])
                        domain = url.split('//')[-1].split('/')[0].replace('www.', '')
                        is_trusted = any(td in domain for td in YANDEX_TRUSTED_DOMAINS)
                        
                        priority = 0.5
                        if is_ru: priority += 0.5
                        if is_trusted: priority += 1.0 # Огромный буст для Алисы
                        if "en.wikipedia.org" in url: priority -= 0.8
                        
                        res['priority_score'] = priority
                        all_results.append(res)
                        seen_urls.add(url)

        if not all_results:
            return []

        all_results.sort(key=lambda x: x.get('priority_score', 0.5), reverse=True)
        results = all_results

        # скрапим страницы
        if status_callback:
            await status_callback(f"Загрузка контента ({min(query_data.scrape_top_n, len(results))} источников)...")

        semaphore = asyncio.Semaphore(10)
        async def sem_scrape(u):
            async with semaphore:
                try:
                    return await asyncio.wait_for(scrape_page(u), timeout=30.0)
                except Exception:
                    return "", {}

        scrape_n = max(query_data.scrape_top_n, DefaultConfigs.SCRAPE_TOP_N)
        scrape_tasks = [sem_scrape(results[i]['url']) for i in range(min(scrape_n, len(results)))]
        
        try:
            # We use a total timeout but also per-page timeout above
            scraped_texts = await asyncio.wait_for(asyncio.gather(*scrape_tasks), timeout=90.0)
        except asyncio.TimeoutError:
            logger.warning("Scraping phase reached global timeout, using partial results")
            # Note: gather with wait_for might raise TimeoutError for all if not小心
            # But here we want to continue with whatever we got if possible.
            # Actually, if TimeoutError is raised, we don't get partial results easily from gather.
            # Let's use return_exceptions=True or similar if we wanted, 
            # but per-page timeout in sem_scrape is already a good guard.
            scraped_texts = [] 
        
        if status_callback:
            await status_callback("Выполняю семантическое ранжирование...")

        all_chunks: List[SearchResult] = []
        for i, res in enumerate(results[:20]):
            content, meta = scraped_texts[i] if i < len(scraped_texts) else ("", {})
            full_text = content if content and len(content) > 200 else res['snippet']
            for passage in self.chunker.split(full_text):
                all_chunks.append(SearchResult(
                    snippet=passage, url=res['url'], title=res['title'], metadata=meta
                ))

        # Тезисы и гибридное ранжирование
        try:
            thesis_res = await self.generation_client.generate_answer(
                prompts.THESIS_EXTRACTION.format(query=query_data.query)
            )
            theses = re.findall(r'\d+\.\s*(.+)', thesis_res)
            theses = [query_data.query] + theses[:4] 
        except Exception:
            theses = [query_data.query]

        ranking_tasks = [self.ranker.rank_chunks(thesis, all_chunks, top_k=7) for thesis in theses]
        results_per_thesis = await asyncio.gather(*ranking_tasks)
        
        seen_snippets = set()
        candidate_passages: List[SearchResult] = []
        for thesis_results in results_per_thesis:
            for p in thesis_results:
                if p.snippet not in seen_snippets:
                    candidate_passages.append(p)
                    seen_snippets.add(p.snippet)
        
        if status_callback:
            await status_callback("Выбираю лучшие источники...")

        # Финальный выбор победителей
        winner_prompt = self._load_prod_prompts().get("WINNER_SELECTION")
        winners = await self.generation_client.select_winners(
            query=query_data.query, candidates=candidate_passages[:25], custom_prompt=winner_prompt
        )
        return winners

    async def _ask_internal(self, query_data: SearchQuery) -> RAGResponse:
        winners = await self._retrieve(query_data)
        if not winners:
            return RAGResponse(answer="Ничего не нашел, сорян.", sources=[])

        context = self._format_context(winners)
        words = context.split()
        if len(words) > DefaultConfigs.MAX_TOTAL_TOKENS:
            context = " ".join(words[:DefaultConfigs.MAX_TOTAL_TOKENS]) + "..."

        system_prompt = prompts.ALICE_SYSTEM if query_data.mode == "alice" else prompts.NEYRO_SYSTEM

        answer = await self.generation_client.generate_answer(
            prompt=f"User Question: {query_data.query}\n\nContext:\n{context}",
            system_prompt=system_prompt
        )
        return RAGResponse(answer=answer, sources=winners)

    def _log_metrics_if_gold(self, query: str, selected_sources: List[SearchResult]):
        """Проверяет наличие запроса в Gold Data и логирует оверлап."""
        try:
            gold_file = "scripts/gold_data.json"
            if os.path.exists(gold_file):
                with open(gold_file, "r", encoding="utf-8") as f:
                    gold_data = json.load(f)
                    match = next((c for c in gold_data if c['query'].lower() == query.lower()), None)
                    if match:
                        self.metric_service.log_overlap(
                            query=query,
                            selected_urls=[s.url for s in selected_sources],
                            expected_urls=match['expected_urls']
                        )
        except Exception as e:
            logger.warning(f"Metric logging failed: {e}")


    def _format_context(self, sources: List[SearchResult]) -> str:
        # просто склеиваем сорсы в один текст
        formatted = []
        for i, s in enumerate(sources, 1):
            formatted.append(f"Source [{i}]: {s.title}\nURL: {s.url}\nText: {s.snippet}")
            
        return "\n---\n".join(formatted)
