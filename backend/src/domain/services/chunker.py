from __future__ import annotations
from typing import List
from src.core.constants import DefaultConfigs

class Chunker:
    def __init__(self, chunk_size: int = None, overlap: int = None) -> None:
        self.chunk_size = chunk_size or DefaultConfigs.CHUNK_SIZE
        self.overlap = overlap or DefaultConfigs.CHUNK_OVERLAP

    def split(self, text: str) -> List[str]:
        if not text:
            return []
            
        words = text.split()
        if len(text) > 4000:
             return [text[i:i+4000] for i in range(0, len(text), 4000)]

        if len(words) <= self.chunk_size:
            return [text]
            
        chunks: List[str] = []
        start = 0
        while start < len(words):
            end = start + self.chunk_size
            chunk_words = words[start:end]
            chunks.append(" ".join(chunk_words))
            
            start += (self.chunk_size - self.overlap)
            
            if len(words) - start <= self.overlap:
                break
                
        return chunks
