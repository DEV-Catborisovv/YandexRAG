import pytest
from unittest.mock import AsyncMock, MagicMock
from src.domain.services.ranker import ChunkRanker
from src.infrastructure.clients.embeddings import YandexEmbeddingsClient
from src.domain.models import SearchResult

# проверяем как ранкер считает косинусы
@pytest.mark.asyncio
async def test_rank_chunks_success():
    mock_client = AsyncMock(spec=YandexEmbeddingsClient)
    
    # эмбеддинг вопроса
    mock_client.get_query_embedding.return_value = [0.1, 0.2]
    # эмбеддинги чанков
    mock_client.get_embeddings.return_value = [
        [0.1, 0.2],  # полное совпадение
        [0.9, 0.0]   # совсем мимо
    ]
    
    ranker = ChunkRanker(embedding_client=mock_client)
    
    chunks = [
        SearchResult(title="т1", url="u1", snippet="с1"),
        SearchResult(title="т2", url="u2", snippet="с2")
    ]
    
    ranked = await ranker.rank_chunks("вопрос", chunks)
    
    assert len(ranked) == 2
    # первый должен быть т1 из-за совпадения эмбеддингов
    assert ranked[0].title == "т1"
    assert ranked[0].score > 0.9
    assert ranked[0].score > ranked[1].score
