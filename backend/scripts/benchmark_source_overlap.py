import asyncio
import json
import logging
from typing import List, Set, Dict
from src.application.rag_service import RAGService
from src.domain.models import SearchQuery
from src.infrastructure.clients.xmlriver import XMLRiverClient
from src.infrastructure.clients.yandex_gpt import YandexGPTClient
from src.infrastructure.clients.embeddings import YandexEmbeddingsClient
from src.domain.services.chunker import Chunker
from src.domain.services.ranker import ChunkRanker
from src.domain.services.source_processor import SourceProcessor
from src.config import Config
from src.core import prompts

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("benchmark")

async def run_benchmark(gold_data_path: str):
    # Валидируем конфиг
    Config.validate()
    
    # Инициализируем компоненты вручную
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
            gold_cases = json.load(f)[:5] # Лимитируем первыми 5 для быстрого теста
    except FileNotFoundError:
        logger.error(f"Файл {gold_data_path} не найден. Создайте его с примерами.")
        return

    results = []
    
    for case in gold_cases:
        query_text = case['query']
        expected_urls = {url.strip('/') for url in case['expected_urls']}
        
        logger.info(f"Тестируем запрос: '{query_text}'")
        
        try:
            # Запускаем наш RAG в режиме alice
            query_data = SearchQuery(query=query_text, mode="alice")
            response = await service.ask(query_data)
            
            def normalize(u):
                return u.split('?')[0].split('#')[0].strip('/').lower().replace('www.', '')

            selected_urls = {normalize(s.url) for s in response.sources}
            expected_urls_norm = {normalize(u) for u in expected_urls}
            
            # Считаем пересечение
            intersection = expected_urls_norm.intersection(selected_urls)
            overlap_count = len(intersection)
            recall = overlap_count / len(expected_urls_norm) if expected_urls_norm else 0
            
            # Считаем семантическое сходство текста
            semantic_sim = 0.0
            llm_evaluation = "N/A"
            
            if "expected_answer" in case:
                # 1. Векторное сходство
                try:
                    v1 = await emb_client.get_query_embedding(response.answer)
                    v2 = await emb_client.get_query_embedding(case["expected_answer"])
                    import numpy as np
                    semantic_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
                except Exception as ex:
                    logger.warning(f"Ошибка при расчете семантического сходства: {ex}")
                
                # 2. Качественная оценка через LLM
                try:
                    comp_prompt = prompts.ANSWER_COMPARISON.format(
                        reference=case["expected_answer"],
                        proposed=response.answer
                    )
                    llm_evaluation = await gpt_client.generate_answer(comp_prompt)
                except Exception as ex:
                    logger.warning(f"Ошибка при LLM-оценке: {ex}")

            results.append({
                "query": query_text,
                "expected_count": len(expected_urls),
                "predicted_count": len(selected_urls),
                "overlap_count": overlap_count,
                "recall": recall,
                "semantic_similarity": float(semantic_sim),
                "llm_evaluation": llm_evaluation,
                "matching_urls": list(intersection),
                "missing_urls": list(expected_urls_norm - selected_urls)
            })
            
            logger.info(f"Overlap: {overlap_count}/{len(expected_urls)} (Recall: {recall:.2%}) | SemSim: {semantic_sim:.2f}")
            if llm_evaluation != "N/A":
                logger.info(f"LLM Judge Score: {llm_evaluation.split('SCORE:')[1].split()[0] if 'SCORE:' in llm_evaluation else '?'}")
            
            # Засыпаем на 2 секунды чтоб не долбить XMLRiver слишком часто
            await asyncio.sleep(2.0)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке '{query_text}': {e}")

    # Итоговая статистика
    if results:
        avg_recall = sum(r['recall'] for r in results) / len(results)
        print("\n" + "="*50)
        print(f"ИТОГОВЫЙ BENCHMARK (N={len(results)})")
        print(f"Средний Recall: {avg_recall:.2%}")
        print("="*50)
        
        with open("benchmark_results.json", "w", encoding='utf-8') as f:
            json.dump({
                "stats": {"avg_recall": avg_recall},
                "details": results
            }, f, ensure_ascii=False, indent=2)
            
if __name__ == "__main__":
    # Для запуска: python -m scripts.benchmark_source_overlap
    asyncio.run(run_benchmark("scripts/gold_data.json"))
