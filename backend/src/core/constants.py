from enum import Enum

class SearchRegion(Enum):
    MOSCOW = 225
    SEARCH_REGION_RU = 225 # Default

class YandexModelNames(Enum):
    GPT_PRO = "yandexgpt-pro"
    GPT_LITE = "yandexgpt-lite"
    EMBEDDING_QUERY = "text-search-query"
    EMBEDDING_DOC = "text-search-doc"

class APIEndpoints:
    XMLRIVER_YANDEX = "https://xmlriver.com/yandex/xml"
    YANDEX_CLOUD_LLM = "llm.api.cloud.yandex.net:443"

class DefaultConfigs:
    RECALL_COUNT = 50 # дефолтные конфиги для всей системы
    
    # чанки и их перекрытие
    CHUNK_SIZE = 128
    CHUNK_OVERLAP = 64
    
    # лимиты токенов для яндекса (в словах)
    MAX_TOKENS_PER_DOC = 800
    MAX_TOTAL_TOKENS = 4000
    
    TOP_K_CHUNKS = 15
    SCRAPE_TOP_N = 15
    
    # минимальный порог для судьи
    JUDGE_MIN_SCORE = 5
