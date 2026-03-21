from __future__ import annotations
import logging
import asyncio
from newspaper import Article

# скрапилка страниц через newspaper4k
# если не грузится — отдаем пустую строку

logger = logging.getLogger(__name__)

async def scrape_page(url: str) -> str:
    try:
        def _fetch():
            article = Article(url)
            article.download()
            article.parse()
            return article.text
            
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, _fetch)
        
        if not text:
            return ""
            
        # чистим лишние пробелы и пустые строки
        lines = (line.strip() for line in text.splitlines())
        text = '\n'.join(line for line in lines if line)
        
        return text
            
    except Exception as e:
        logger.warning(f"Failed to scrape {url}: {e}")
        return ""
