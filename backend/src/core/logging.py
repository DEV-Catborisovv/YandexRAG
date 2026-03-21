from __future__ import annotations
import logging
import json
from datetime import datetime
from typing import Any

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        if hasattr(record, "context"):
            log_record["context"] = record.context
            
        return json.dumps(log_record, ensure_ascii=False)

def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    
    logger = logging.getLogger("YandexRAG")
    logger.setLevel(level)
    logger.addHandler(handler)
    
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("yandex_cloud_ml_sdk").setLevel(logging.WARNING)
