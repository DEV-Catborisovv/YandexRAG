import asyncio
import logging
from src.infrastructure.utils.scraper import scrape_page
from src.config import Config

logging.basicConfig(level=logging.INFO)

async def test_scrapfly():
    # Яндекс.Карты часто блокируют даже Playwright Stealth в серверном окружении
    url = "https://yandex.ru/maps/discovery/podborka_gostinica_kazan-43/"
    print(f"Testing scraper for: {url}")
    
    text, metadata = await scrape_page(url)
    
    print("\n--- Metadata ---")
    print(metadata)
    
    print("\n--- Content Preview (first 500 chars) ---")
    if text:
        print(text[:500])
        print(f"\nTotal length: {len(text)}")
    else:
        print("FAILED: No text recovered.")

if __name__ == "__main__":
    Config.validate()
    asyncio.run(test_scrapfly())
