import asyncio
import json
import logging
import os
import time
from typing import List, Dict, Any
from src.application.rag_service import RAGService
from src.domain.models import SearchQuery
from src.infrastructure.clients.xmlriver import XMLRiverClient
from src.infrastructure.clients.yandex_gpt import YandexGPTClient
from src.infrastructure.clients.embeddings import YandexEmbeddingsClient
from src.domain.services.chunker import Chunker
from src.domain.services.ranker import ChunkRanker
from src.domain.services.source_processor import SourceProcessor
from src.config import Config

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("extended_benchmark")

async def run_extended_benchmark(gold_data_path: str, output_path: str = "benchmark_results.json"):
    Config.validate()
    
    # Инициализация сервисов
    search_client = XMLRiverClient(user_id=Config.XMLRIVER_USER_ID, api_key=Config.XMLRIVER_KEY)
    emb_client = YandexEmbeddingsClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)
    gpt_client = YandexGPTClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)
    chunker = Chunker()
    ranker = ChunkRanker(embedding_client=emb_client)
    processor = SourceProcessor(chunker=chunker, ranker=ranker)
    
    service = RAGService(
        search_client=search_client,
        ranker=ranker,
        generation_client=gpt_client,
        chunker=chunker,
        source_processor=processor
    )

    try:
        with open(gold_data_path, 'r', encoding='utf-8') as f:
            gold_cases = json.load(f)
        logger.info(f"Loaded {len(gold_cases)} gold cases from {gold_data_path}")
    except Exception as e:
        logger.error(f"Failed to load gold data: {e}")
        return

    results = []
    start_time = time.time()

    def normalize(u):
        if not u: return ""
        return u.split('?')[0].split('#')[0].strip('/').lower().replace('www.', '')

    for i, case in enumerate(gold_cases):
        query_text = case['query']
        expected_urls = {normalize(u) for u in case.get('expected_urls', [])}
        
        logger.info(f"[{i+1}/{len(gold_cases)}] Testing: '{query_text}'")
        
        try:
            query_data = SearchQuery(query=query_text, mode="alice")
            response = await service.ask(query_data)
            
            selected_urls = {normalize(s.url) for s in response.sources}
            intersection = expected_urls.intersection(selected_urls)
            overlap_count = len(intersection)
            recall = overlap_count / len(expected_urls) if expected_urls else 0
            
            results.append({
                "query": query_text,
                "expected_urls": list(expected_urls),
                "selected_urls": list(selected_urls),
                "overlap_count": overlap_count,
                "recall": recall,
                "success": True
            })
            
            logger.info(f"  Recall: {recall:.2%} ({overlap_count}/{len(expected_urls)})")
            
            # Anti-throttle sleep
            await asyncio.sleep(1.0)
            
        except Exception as e:
            logger.error(f"  Error processing '{query_text}': {e}")
            results.append({
                "query": query_text,
                "success": False,
                "error": str(e)
            })

    total_time = time.time() - start_time
    valid_results = [r for r in results if r['success']]
    avg_recall = sum(r['recall'] for r in valid_results) / len(valid_results) if valid_results else 0
    
    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_cases": len(gold_cases),
        "processed_cases": len(valid_results),
        "avg_recall": avg_recall,
        "total_time_sec": total_time,
        "details": results
    }

    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    logger.info("="*50)
    logger.info(f"BENCHMARK COMPLETE")
    logger.info(f"Average Recall: {avg_recall:.2%}")
    logger.info(f"Results saved to {output_path}")
    logger.info("="*50)

if __name__ == "__main__":
    import sys
    gold_path = sys.argv[1] if len(sys.argv) > 1 else "scripts/gold_data.json"
    asyncio.run(run_extended_benchmark(gold_path))
