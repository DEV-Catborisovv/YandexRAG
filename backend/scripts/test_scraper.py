import asyncio
import logging
from src.infrastructure.utils.scraper import scrape_page

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_scraper():
    test_urls = [
        "https://www.avito.ru/moskva/predlozheniya_uslug/remont_kvartir_pod_klyuch_ot_chastnika_2154381395",
        "https://irecommend.ru/content/nash-opyt-arendy-v-kaliningrade",
        "https://www.rbc.ru/business/26/03/2026/671db5ac979d2115d85b4e04"
    ]

    print("\n--- Testing SmartScraper Anti-Bot --- \n")
    for url in test_urls:
        print(f"Scraping: {url}...")
        text, meta = await scrape_page(url)
        
        status = "SUCCESS" if text else "FAILED"
        blocked = meta.get("blocked", False)
        print(f"Result: {status} (Blocked detected: {blocked})")
        if text:
            print(f"Text snippet: {text[:200]}...")
        print("-" * 50)

if __name__ == "__main__":
    # asyncio.run(test_geo()) # Wait, wrong function name in my head
    asyncio.run(test_scraper())
