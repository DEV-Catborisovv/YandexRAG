import logging
import asyncio
import random
import re
from typing import Tuple, Dict, Any, List
from newspaper import Article
from bs4 import BeautifulSoup
import httpx
from src.config import Config

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Домены, которые точно требуют прокси/анти-бот (тяжелые агрегаторы)
HEAVY_DOMAINS = ["avito.ru", "zoon.ru", "auto.ru", "tripadvisor", "2gis", "maps.yandex", "cian.ru"]

async def _scrape_httpx(url: str) -> str:
    """Fallback scraping using standard httpx with rotating User-Agent."""
    logger.info(f"SmartScraper: Fallback HTTPX for {url}")
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": random.choice(USER_AGENTS)}
        ) as client:
            response = await client.get(url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "lxml")
                for script in soup(["script", "style", "nav", "footer"]):
                    script.extract()
                return soup.get_text(separator='\n')
    except Exception as e:
        logger.warning(f"Fallback HTTPX failed for {url}: {e}")
    return ""

async def _scrape_scrapfly(url: str) -> str:
    """Ультимативный скрапинг через Scrapfly API (Resident Proxies + Anti-Bot)."""
    if not Config.SCRAPFLY_API_KEY:
        logger.warning("Scrapfly API key is missing.")
        return ""

    logger.info(f"SmartScraper: Calling Scrapfly for {url}")
    params = {
        "key": Config.SCRAPFLY_API_KEY,
        "url": url,
        "asp": "true", # Anti-Scraping Protection bypass
        "render_js": "true",
        "proxy_pool": "public_residential_pool", # Испольуем резидентские прокси для РФ сайтов
        "country": "ru" # Важно для Авито/Яндекса
    }

    max_retries = 3 
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.get("https://api.scrapfly.io/scrape", params=params)

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2 + random.uniform(0, 1)
                        logger.warning(f"Scrapfly 429 (Too Many Requests), retrying in {wait_time:.1f}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Scrapfly 429 persistent for {url}. Switching to fallback.")
                        return await _scrape_httpx(url)

                if response.status_code == 422:
                    # 422 often means upstream timeout or block that won't be fixed by simple retry
                    logger.warning(f"Scrapfly 422 (Upstream Error) for {url}. Attempting one-time retry without proxy/country.")
                    if "proxy_pool" in params:
                        params.pop("proxy_pool", None)
                        params.pop("country", None)
                        continue # Retry once without these params
                    else:
                        logger.error(f"Scrapfly 422 persistent for {url}. Switching to fallback.")
                        return await _scrape_httpx(url)

                response.raise_for_status()

                data = response.json()
                result = data.get("result", {})
                
                # Check for success in the result object even if status is 200
                if not result.get("success", False):
                    error_msg = result.get("error", {}).get("message", "Unknown Scrapfly Error")
                    logger.warning(f"Scrapfly reported failure for {url}: {error_msg}")
                    if "UPSTREAM_TIMEOUT" in error_msg or "403" in error_msg:
                         return await _scrape_httpx(url)
                    continue

                content = result.get("content", "")
                logger.info(f"Scrapfly: Received {len(content)} characters of HTML.")

                if not content or len(content) < 200:
                    logger.warning(f"Scrapfly: Insufficient content for {url}")
                    return await _scrape_httpx(url)

                soup = BeautifulSoup(content, "lxml")
                for script in soup(["script", "style", "nav", "footer"]):
                    script.extract()

                text = soup.get_text(separator='\n')
                return text
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Scrapfly error (attempt {attempt+1}): {e}. Retrying...")
                await asyncio.sleep(1)
                continue
            logger.error(f"Scrapfly failed for {url}: {e}. Switching to fallback.")
            return await _scrape_httpx(url)
    return ""
    return ""

async def scrape_page(url: str) -> Tuple[str, Dict[str, Any]]:
    metadata = {
        "has_phone": False,
        "has_address": False,
        "table_count": 0,
        "list_count": 0,
        "header_count": 0,
        "is_aggregator": any(domain in url for domain in ["zoon.ru", "2gis", "maps.yandex", "tripadvisor", "avito", "otzovik", "irecommend"]),
        "blocked": False,
        "source": "unknown"
    }

    # 1. Если домен тяжелый — сразу идем в Scrapfly (with fallback)
    if any(domain in url for domain in HEAVY_DOMAINS):
        logger.info(f"SmartScraper: {url} is a heavy domain, using Scrapfly.")
        text = await _scrape_scrapfly(url)
        metadata["source"] = "scrapfly"
        if text:
            lines = (line.strip() for line in text.splitlines())
            return '\n'.join(line for line in lines if line and len(line) > 20), metadata
        return "", metadata

    # 2. Пробуем Newspaper4k (Fast)
    try:
        def _fetch_standard():
            article = Article(url)
            article.config.browser_user_agent = random.choice(USER_AGENTS)
            article.config.request_timeout = 10
            article.download()

            if not article.html or len(article.html) < 500:
                 return None

            article.parse()
            return article

        loop = asyncio.get_running_loop()
        article = await loop.run_in_executor(None, _fetch_standard)

        if article and article.text and len(article.text) > 500:
            metadata["source"] = "newspaper"
            # Парсим метаданные
            soup = BeautifulSoup(article.html, "lxml")
            phone_pattern = r'(\+7|8)[\s\-\(]*[0-9]{3}[\s\-\)]*[0-9]{3}[\s\-]*[0-9]{2}[\s\-]*[0-9]{2}'
            address_pattern = r'(ул\.|улица|пр-т|проспект|д\.|дом)\s+[А-Яа-я0-9]'

            html_content = article.html.lower()
            metadata["has_phone"] = bool(re.search(phone_pattern, html_content))
            metadata["has_address"] = bool(re.search(address_pattern, html_content))
            metadata["table_count"] = len(soup.find_all("table"))
            metadata["list_count"] = len(soup.find_all(["ul", "ol"]))
            metadata["header_count"] = len(soup.find_all(["h1", "h2", "h3"]))

            lines = (line.strip() for line in article.text.splitlines())
            return '\n'.join(line for line in lines if line and len(line) > 20), metadata

    except Exception as e:
        logger.warning(f"Standard scrape failed for {url}: {e}")

    # 3. Last Resort: Scrapfly (with auto-fallback to httpx inside)
    logger.info(f"SmartScraper: Final fallback for {url}")
    text = await _scrape_scrapfly(url)
    metadata["source"] = "fallback"
    if text:
        lines = (line.strip() for line in text.splitlines())
        clean_text = '\n'.join(line for line in lines if line and len(line) > 20)
        return clean_text, metadata
    return "", metadata
