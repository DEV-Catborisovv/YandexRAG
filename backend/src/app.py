from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import rag
from src.config import Config
from src.core.logging import setup_logging

setup_logging()
Config.validate()

# создаем фастапи экземпляр
app = FastAPI(
    title="YandexRAG API",
    description="Нейро-поиск с Яндекс GPT",
    version="1.0.0"
)

# настраиваем корсы чтоб фронт мог стучаться
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag.router)


@app.get("/")
async def root():
    return {"status": "ok", "msg": "YandexRAG is running"}
