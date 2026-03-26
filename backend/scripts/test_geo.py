import asyncio
import logging
from src.domain.services.geo_service import GeoService
from src.infrastructure.clients.yandex_gpt import YandexGPTClient
from src.config import Config

logging.basicConfig(level=logging.INFO)

async def test_geo():
    # Setup
    gpt_client = YandexGPTClient(folder_id=Config.YANDEX_FOLDER_ID, api_key=Config.YANDEX_API_KEY)
    geo_service = GeoService(generation_client=gpt_client)

    test_queries = [
        "рестораны в Казани",
        "прокат авто в калининграде отзывы",
        "лучшие фитнес-клубы Санкт-Петербурга",
        "где погулять в уфе с детьми",
        "доставка цветов краснодар",
        "ремонт квартир в москве",
        "что посмотреть на Алтае"
    ]

    print("\n--- Testing GeoService Extraction ---\n")
    for query in test_queries:
        code = await geo_service.extract_region_code(query)
        print(f"Query: '{query}' -> Region Code: {code}")

if __name__ == "__main__":
    asyncio.run(test_geo())
