import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class MetricService:
    def __init__(self, metrics_file: str = "metrics_log.json"):
        self.metrics_file = metrics_file
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.metrics_file):
            with open(self.metrics_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _normalize_url(self, url: str) -> str:
        """Чистит URL от протоколов, параметров и фрагментов."""
        u = url.split('?')[0].split('#')[0].strip('/').lower()
        for prefix in ["https://", "http://", "www."]:
            if u.startswith(prefix):
                u = u[len(prefix):]
        return u

    def log_overlap(self, query: str, selected_urls: List[str], expected_urls: List[str]):
        """Расчет и логирование Recall@K (Overlap) с поддержкой Smart Matching."""
        sel = [self._normalize_url(u) for u in selected_urls]
        exp = [self._normalize_url(u) for u in expected_urls]
        
        if not exp:
            return 0.0
            
        intersection_count = 0
        for g_url in exp:
            # Префиксное совпадение: если предсказанный URL начинается с эталонного
            # (например, kp.ru/russia/ -> kp.ru/russia/any-page)
            matched = False
            for p_url in sel:
                if p_url == g_url or p_url.startswith(g_url + '/'):
                    matched = True
                    break
            if matched:
                intersection_count += 1

        recall = intersection_count / len(exp)
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "recall": recall,
            "intersection_count": intersection_count,
            "expected_count": len(exp),
            "selected_count": len(sel)
        }
        
        self._save_entry(entry)
        logger.info(f"Logged metric for '{query}': Overlap={recall:.2%}")
        return recall

    def _save_entry(self, entry: Dict[str, Any]):
        try:
            with open(self.metrics_file, "r+", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    # Если файл поврежден, сбрасываем в пустой список
                    data = []
                
                data.append(entry)
                f.seek(0)
                json.dump(data[-100:], f, indent=4, ensure_ascii=False)
                f.truncate()
        except Exception as e:
            logger.error(f"Failed to save metric entry: {e}")
    def get_average_recall(self) -> float:
        try:
            with open(self.metrics_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not data:
                    return 0.0
                return sum(e["recall"] for e in data) / len(data)
        except Exception:
            return 0.0
