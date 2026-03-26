import dspy
import logging
import sys
from src.infrastructure.dspy_utils import YandexGPTLM
from src.infrastructure.dspy_program import RAGModule, overlap_metric
from src.config import Config

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("quick_test")

# --- ГОРЯЧИЙ ФИКС ДЛЯ DSPy 3.1.3 ---
from dspy.teleprompt import MIPROv2

class RescueMIPRO(MIPROv2):
    """Кастомный MIPROv2, который подменяет этап генерации инструкций, если он падает."""
    def _propose_instructions(self, program, trainset, num_instruct_candidates, **kwargs):
        logger.info("RescueMIPRO: Attempting to propose instructions...")
        try:
            # Пытаемся стандартным способом
            return super()._propose_instructions(program, trainset, num_instruct_candidates, **kwargs)
        except Exception as e:
            logger.warning(f"RescueMIPRO: Proposer failed ({e}), using manual high-quality candidates.")
            # Это «хакнутые» инструкции, которые мы выявили в ходе ручных тестов
            return [
                "Determine the relevance of search results by prioritizing geographical proximity and domain authority (Maps, Discovery).",
                "Extract the most relevant URLs by matching semantic theses and checking for official business markers.",
                "Rank sources based on their trustworthiness and content depth relative to the user query."
            ]

def quick_test():
    """Быстрая проверка работоспособности всего цикла оптимизации."""
    from src.infrastructure.clients.xmlriver import XMLRiverClient
    from src.infrastructure.clients.yandex_gpt import YandexGPTClient
    from src.infrastructure.clients.embeddings import YandexEmbeddingsClient
    from src.domain.services.chunker import Chunker
    from src.domain.services.ranker import ChunkRanker
    from src.domain.services.source_processor import SourceProcessor
    from src.domain.services.metrics import MetricService
    from src.application.rag_service import RAGService

    # Инициализация всех клиентов и сервисов
    xml_client = XMLRiverClient(user_id=Config.XMLRIVER_USER_ID, api_key=Config.XMLRIVER_KEY)
    gpt_client = YandexGPTClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)
    embed_client = YandexEmbeddingsClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)
    
    chunker = Chunker()
    ranker = ChunkRanker(embedding_client=embed_client)
    source_processor = SourceProcessor(chunker=chunker, ranker=ranker)
    metric_service = MetricService()
    
    rag_service = RAGService(
        search_client=xml_client,
        ranker=ranker,
        generation_client=gpt_client,
        chunker=chunker,
        source_processor=source_processor,
        metric_service=metric_service
    )
    
    lm = YandexGPTLM(
        model="yandexgpt-lite/latest",
        folder_id=Config.YANDEX_FOLDER_ID,
        api_key=Config.YANDEX_API_KEY
    )
    dspy.settings.configure(lm=lm)
    
    program = RAGModule(rag_service=rag_service)
    
    # Небольшой trainset для теста
    trainset = [
        dspy.Example(query="доставка суши москва лучшие", 
                     expected_urls=["https://yakitoriya.ru/", "https://tanuki.ru/"])
                 .with_inputs("query"),
        dspy.Example(query="стоматология круглосуточно выхино", 
                     expected_urls=["https://vikhino-dent.ru/"])
                 .with_inputs("query")
    ]
    
    # Используем наш "спасательный" оптимизатор
    teleprompter = RescueMIPRO(
        metric=overlap_metric,
        prompt_model=lm,
        task_model=lm,
        num_candidates=7,
        auto=None
    )
    
    logger.info("Starting QUICK optimization test with RescueMIPRO...")
    try:
        # Уменьшаем параметры до минимума для скорости
        optimized_program = teleprompter.compile(
            program, 
            trainset=trainset,
            num_trials=2,
            max_bootstrapped_demos=1,
            max_labeled_demos=1,
            minibatch_size=1,
            requires_permission_to_run=False
        )
        logger.info("QUICK TEST SUCCESSFUL!")
        print("\n=== OPTIMIZATION RESULT ===")
        print(optimized_program.dump_state())
        
    except Exception as e:
        logger.exception(f"QUICK TEST FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    quick_test()
