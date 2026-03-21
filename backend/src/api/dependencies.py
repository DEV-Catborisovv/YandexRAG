from fastapi import Depends
from src.config import Config
from src.infrastructure.clients.xmlriver import XMLRiverClient
from src.infrastructure.clients.yandex_gpt import YandexGPTClient
from src.infrastructure.clients.embeddings import YandexEmbeddingsClient
from src.domain.services.chunker import Chunker
from src.domain.services.ranker import ChunkRanker
from src.domain.services.source_processor import SourceProcessor
from src.application.rag_service import RAGService

# тут инъекция зависимостей для фастапи

def get_xmlriver_client():
    return XMLRiverClient(user_id=Config.XMLRIVER_USER_ID, api_key=Config.XMLRIVER_KEY)

def get_embeddings_client():
    return YandexEmbeddingsClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)

def get_yandex_gpt_client():
    return YandexGPTClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)

def get_chunker():
    return Chunker()

def get_ranker(emb: YandexEmbeddingsClient = Depends(get_embeddings_client)):
    return ChunkRanker(embedding_client=emb)

def get_source_processor(
    c: Chunker = Depends(get_chunker),
    r: ChunkRanker = Depends(get_ranker)
):
    return SourceProcessor(chunker=c, ranker=r)


def get_rag_service(
    s: XMLRiverClient = Depends(get_xmlriver_client),
    r: ChunkRanker = Depends(get_ranker),
    g: YandexGPTClient = Depends(get_yandex_gpt_client),
    c: Chunker = Depends(get_chunker),
    p: SourceProcessor = Depends(get_source_processor)
):
    return RAGService(
        search_client=s,
        ranker=r,
        generation_client=g,
        chunker=c,
        source_processor=p
    )
