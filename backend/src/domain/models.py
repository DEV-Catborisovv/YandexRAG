from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from src.core.constants import DefaultConfigs

# модельки данных

class SearchResult(BaseModel):
    title: str = Field(...)
    url: str = Field(...)
    snippet: str = Field(...)
    score: Optional[float] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("пустая строка")
        return v.strip()


class SearchQuery(BaseModel):
    query: str = Field(...)
    history: List[Dict[str, str]] = Field(default_factory=list)
    scrape_top_n: int = Field(default=DefaultConfigs.SCRAPE_TOP_N, ge=0, le=20)
    mode: str = Field(default="neyro") # neyro or alice


class RAGResponse(BaseModel):
    answer: str = Field(...)
    sources: List[SearchResult] = Field(default_factory=list)

    @field_validator("answer")
    @classmethod
    def answer_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ответ пустой")
        return v.strip()
