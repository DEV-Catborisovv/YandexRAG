import logging
from lxml import etree
from typing import List, Dict, Any

# парсим ответ от xmlriver
# юзаем lxml чтоб быстрее было

logger = logging.getLogger(__name__)

def parse_xml_river_response(xml_content: str) -> List[Dict[str, Any]]:
    try:
        # юзаем HTMLParser тк яндекс может вернуть странные сущности
        parser = etree.HTMLParser(recover=True, encoding='utf-8')
        root = etree.fromstring(xml_content.encode('utf-8'), parser=parser)
        
        results: List[Dict[str, Any]] = []
        
        # ищем все <doc> в ответе
        docs = root.xpath('//doc')
        for doc in docs:
            title_node = doc.xpath('./title')
            snippet_node = doc.xpath('./snippet')
            url_node = doc.xpath('./url')
            
            title = "".join(title_node[0].itertext()) if title_node else ""
            snippet = "".join(snippet_node[0].itertext()) if snippet_node else ""
            url = url_node[0].text if url_node else ""
            
            if not title and not url:
                continue

            results.append({
                "title": title.strip(),
                "snippet": snippet.strip(),
                "url": url.strip() if url else ""
            })
            
        return results
    except Exception:
        logger.exception("ошибка парсинга xmlriver")
        return []
