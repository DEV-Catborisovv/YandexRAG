import re
import logging
from typing import Optional, Dict
from src.infrastructure.clients.yandex_gpt import YandexGPTClient

logger = logging.getLogger(__name__)

# Основные регионы Яндекс (lr)
YANDEX_REGIONS: Dict[str, int] = {
    "москва": 213,
    "московская": 1,
    "санкт-петербург": 2,
    "питер": 2,
    "спб": 2,
    "ленинградская": 10174,
    "новосибирск": 65,
    "екатеринбург": 54,
    "нижний новгород": 47,
    "казань": 43,
    "челябинск": 56,
    "омск": 66,
    "самара": 51,
    "ростов-на-дону": 39,
    "уфа": 172,
    "красноярск": 62,
    "пермь": 50,
    "воронеж": 193,
    "волгоград": 38,
    "краснодар": 35,
    "калининград": 22,
    "сочи": 239,
    "алтай": 11316,
    "крым": 977,
}

class GeoService:
    def __init__(self, generation_client: YandexGPTClient):
        self.generation_client = generation_client

    async def extract_region_code(self, query: str) -> int:
        """
        Извлекает город/регион из запроса и возвращает код lr для Яндекса.
        Если регион не найден, возвращает 225 (вся Россия).
        """
        query_lower = query.lower()
        
        # 1. Пробуем поиск по словарю с учетом окончаний (простой стемминг)
        for city, code in YANDEX_REGIONS.items():
            # Если город в именительном падеже есть в запросе или запрос содержит основу города
            # (например "москв" для "в москве")
            stem = city[:-1] if len(city) > 4 else city
            if stem in query_lower:
                logger.info(f"GeoService: Found match for '{city}' (stem '{stem}') in query. Region code: {code}")
                return code

        # 2. Если не нашли, просим LLM вытащить город
        # Используем более строгую инструкцию
        prompt = f"USER_QUERY: {query}\n\nTask: Extract the city name from the user query. Output ONLY the city name in nominative case (e.g., 'Москва'). If no city is specified, output 'Россия'."
        
        try:
            raw_response = await self.generation_client.generate_answer(prompt)
            # Очищаем ответ: берем только осмысленную часть (иногда LLM повторяет вопрос)
            # Ищем последнее слово или строку, которая похожа на город
            lines = [line.strip() for line in raw_response.split('\n') if line.strip()]
            if not lines:
                return 225
                
            extracted_city = lines[-1].lower().replace(".", "").replace("!", "").split()[-1]
            
            logger.info(f"GeoService: LLM raw response filtered to: '{extracted_city}'")
            
            # Проверяем по словарю еще раз после LLM
            if extracted_city in YANDEX_REGIONS:
                return YANDEX_REGIONS[extracted_city]
            
            # Если город экзотический и его нет в словаре, можно было бы сделать доп. запрос к API Яндекса 
            # для получения кода региона, но пока ограничимся этим.
            return 225
            
        except Exception as e:
            logger.warning(f"GeoService: Failed to extract region via LLM: {e}")
            return 225
