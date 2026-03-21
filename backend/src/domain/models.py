from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict
from src.core.constants import DefaultConfigs

# модельки данных

class SearchResult(BaseModel):
    title: str = Field(...)
    url: str = Field(...)
    snippet: str = Field(...)
    score: Optional[float] = Field(None)

    @field_validator("title", "snippet")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("пустая строка")
        return v.strip()


class SearchQuery(BaseModel):
    query: str = Field(...)
    history: List[Dict[str, str]] = Field(default_factory=list)
    scrape_top_n: int = Field(default=DefaultConfigs.SCRAPE_TOP_N, ge=0, le=20)


class RAGResponse(BaseModel):
    answer: str = Field(...)
    sources: List[SearchResult] = Field(default_factory=list)

    @field_validator("answer")
    @classmethod
    def answer_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ответ пустой")
        return v.strip()
