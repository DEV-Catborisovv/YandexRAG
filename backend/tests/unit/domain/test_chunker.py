import pytest
from src.domain.services.chunker import Chunker

def test_chunker_empty_string():
    chunker = Chunker(chunk_size=5, overlap=2)
    assert chunker.split("") == []

def test_chunker_small_text():
    chunker = Chunker(chunk_size=10, overlap=2)
    text = "Hello world this is a small text"
    assert chunker.split(text) == [text]

# тестим нарезку текста на куски
def test_chunking_logic():
    # 10 слов
    text = "раз два три четыре пять шесть семь восемь девять десять"
    chunker = Chunker(chunk_size=5, overlap=2)
    
    chunks = chunker.split(text)
    
    # первый чанк: раз...пять
    # второй: четыре...восемь (нахлест 2 слова)
    # третий: семь...десять
    assert len(chunks) == 3
    assert chunks[0] == "раз два три четыре пять"
    assert chunks[1] == "четыре пять шесть семь восемь"
    assert chunks[2] == "семь восемь девять десять"

def test_chunker_splitting():
    chunker = Chunker(chunk_size=5, overlap=2)
    text = "one two three four five six seven eight nine ten"
    # c1: one two three four five
    # next start = 5 - 2 = 3
    # c2: four five six seven eight
    # next start = 3 + 5 - 2 = 6
    # c3: seven eight nine ten
    chunks = chunker.split(text)
    assert len(chunks) == 3
    assert "one two three four five" in chunks[0]
    assert "four five six seven eight" in chunks[1]
    assert "seven eight nine ten" in chunks[2]
