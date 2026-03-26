from fastapi import Depends
from src.config import Config
from src.infrastructure.clients.xmlriver import XMLRiverClient
from src.infrastructure.clients.yandex_gpt import YandexGPTClient
from src.infrastructure.clients.embeddings import YandexEmbeddingsClient
from src.domain.services.chunker import Chunker
from src.domain.services.ranker import ChunkRanker
from src.domain.services.source_processor import SourceProcessor
from src.domain.services.metrics import MetricService
from src.domain.services.geo_service import GeoService
from src.application.rag_service import RAGService

# тут инъекция зависимостей для фастапи

def get_metric_service():
    return MetricService()

def get_xmlriver_client():
    return XMLRiverClient(user_id=Config.XMLRIVER_USER_ID, api_key=Config.XMLRIVER_KEY)

def get_embeddings_client():
    return YandexEmbeddingsClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)

def get_yandex_gpt_client():
    return YandexGPTClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)

def get_chunker():
    return Chunker()

from src.domain.services.ranker import ChunkRanker, CrossEncoderRanker
from src.domain.services.source_processor import SourceProcessor

def get_ranker(emb: YandexEmbeddingsClient = Depends(get_embeddings_client)):
    # BAAI/bge-reranker-base is a good default for Russian-segment RAG
    ce = CrossEncoderRanker(model_name="BAAI/bge-reranker-base")
    return ChunkRanker(embedding_client=emb, cross_encoder=ce)

def get_source_processor(
    c: Chunker = Depends(get_chunker),
    r: ChunkRanker = Depends(get_ranker)
):
    return SourceProcessor(chunker=c, ranker=r)

def get_geo_service(g: YandexGPTClient = Depends(get_yandex_gpt_client)):
    return GeoService(generation_client=g)


def get_rag_service(
    s: XMLRiverClient = Depends(get_xmlriver_client),
    r: ChunkRanker = Depends(get_ranker),
    g: YandexGPTClient = Depends(get_yandex_gpt_client),
    c: Chunker = Depends(get_chunker),
    p: SourceProcessor = Depends(get_source_processor),
    m: MetricService = Depends(get_metric_service),
    geo: GeoService = Depends(get_geo_service)
):
    return RAGService(
        search_client=s,
        ranker=r,
        generation_client=g,
        chunker=c,
        source_processor=p,
        metric_service=m,
        geo_service=geo
    )
