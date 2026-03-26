from __future__ import annotations
import os
from dotenv import load_dotenv
from src.domain.exceptions import ConfigurationException
from src.core.constants import DefaultConfigs


# грузим переменные окружения из .env
load_dotenv()

class Config:
    # ключи для яндекса и xmlriver
    YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
    YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
    
    XMLRIVER_USER_ID = os.getenv("XMLRIVER_USER_ID")
    XMLRIVER_KEY = os.getenv("XMLRIVER_KEY")
    SCRAPFLY_API_KEY = os.getenv("SCRAPFLY_API_KEY")
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))


    @classmethod
    def validate(cls):
        # чекаем чтоб все было на месте
        missing = [
            k for k, v in {
                "YANDEX_API_KEY": cls.YANDEX_API_KEY,
                "YANDEX_FOLDER_ID": cls.YANDEX_FOLDER_ID,
                "XMLRIVER_USER_ID": cls.XMLRIVER_USER_ID,
                "XMLRIVER_KEY": cls.XMLRIVER_KEY
            }.items() if not v
        ]
        if missing:
            raise ValueError(f"Missing env vars: {', '.join(missing)}")
