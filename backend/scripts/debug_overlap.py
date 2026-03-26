import asyncio
import json
from src.infrastructure.clients.xmlriver import XMLRiverClient
from src.infrastructure.clients.yandex_gpt import YandexGPTClient
from src.infrastructure.clients.embeddings import YandexEmbeddingsClient
from src.domain.services.chunker import Chunker
from src.domain.services.ranker import ChunkRanker
from src.domain.services.source_processor import SourceProcessor
from src.domain.services.metrics import MetricService
from src.application.rag_service import RAGService
from src.infrastructure.dspy_utils import YandexGPTLM
from src.config import Config
from src.infrastructure.dspy_program import overlap_metric, RAGModule
import dspy

async def debug_one():
    # Setup
    xml_client = XMLRiverClient(user_id=Config.XMLRIVER_USER_ID, api_key=Config.XMLRIVER_KEY)
    emb_client = YandexEmbeddingsClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)
    gpt_client = YandexGPTClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)
    lm = YandexGPTLM(model="yandexgpt-lite/latest", folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)
    dspy.settings.configure(lm=lm)
    
    chunker = Chunker()
    ranker = ChunkRanker(embedding_client=emb_client)
    processor = SourceProcessor(chunker=chunker, ranker=ranker)
    metrics = MetricService()
    
    service = RAGService(xml_client, ranker, gpt_client, chunker, processor, metrics)
    program = RAGModule(service, lm=lm)
    
    # Gold data
    with open("scripts/gold_data.json", "r", encoding="utf-8") as f:
        gold = json.load(f)[0]
    
    print(f"Testing Query: {gold['query']}")
    print(f"Gold URLs: {gold['expected_urls']}")
    
    # Run prediction
    pred = program(query=gold['query'])
    print(f"Predicted URLs: {pred.urls}")
    
    # Check overlap
    example = dspy.Example(query=gold['query'], expected_urls=gold['expected_urls'])
    score = overlap_metric(example, pred)
    print(f"Overlap Score: {score}")

if __name__ == "__main__":
    asyncio.run(debug_one())
