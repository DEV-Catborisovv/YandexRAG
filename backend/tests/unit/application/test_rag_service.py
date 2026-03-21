import pytest
from unittest.mock import AsyncMock, MagicMock
from src.application.rag_service import RAGService
from src.domain.models import SearchQuery, RAGResponse, SearchResult

# тестим раг сервис целиком
# мокаем все тяжелое

@pytest.mark.asyncio
async def test_rag_service_ask():
    # 1. моки
    mock_search = AsyncMock()
    mock_ranker = AsyncMock()
    mock_gpt = AsyncMock()
    mock_chunker = MagicMock()
    mock_processor = AsyncMock()

    mock_search.search.return_value = [{"title": "Заголовок 1", "url": "http://ya.ru", "snippet": "текст"}]
    mock_chunker.split.return_value = ["чанк 1"]
    mock_ranker.rank_chunks.return_value = [
        SearchResult(title="Заголовок 1", url="http://ya.ru", snippet="чанк 1", score=0.9)
    ]
    mock_gpt.score_passage.return_value = 9
    mock_gpt.select_winners.return_value = [
        SearchResult(title="Заголовок 1", url="http://ya.ru", snippet="чанк 1", score=0.9)
    ]
    mock_gpt.generate_answer.return_value = "Ответ от ГПТ"
    mock_gpt.rephrase_query.return_value = "перефразированный запрос"
    mock_gpt.verify_answer.return_value = (True, "")
    
    mock_processor.process_document.side_effect = lambda q, d: d

    service = RAGService(
        search_client=mock_search,
        ranker=mock_ranker,
        generation_client=mock_gpt,
        chunker=mock_chunker,
        source_processor=mock_processor
    )

    query = SearchQuery(query="тестовый вопрос", scrape_top_n=0)
    response = await service.ask(query)

    assert response.answer == "Ответ от ГПТ"
    assert len(response.sources) == 1


@pytest.mark.asyncio
async def test_rag_service_filtering():
    mock_search = AsyncMock()
    mock_ranker = AsyncMock()
    mock_gpt = AsyncMock()
    mock_chunker = MagicMock()
    mock_processor = AsyncMock()

    mock_search.search.return_value = [{"title": "Т1", "url": "U1", "snippet": "S1"}]
    mock_chunker.split.return_value = ["C1"]
    mock_ranker.rank_chunks.return_value = [
        SearchResult(title="Т1", url="U1", snippet="C1", score=0.9)
    ]
    # низкая оценка (5)
    mock_gpt.score_passage.return_value = 5
    mock_gpt.rephrase_query.return_value = "запрос"
    mock_gpt.select_winners.return_value = []
    mock_gpt.generate_answer.return_value = "Инфы мало, не могу ответить."
    mock_gpt.verify_answer.return_value = (True, "")

    service = RAGService(
        search_client=mock_search,
        ranker=mock_ranker,
        generation_client=mock_gpt,
        chunker=mock_chunker,
        source_processor=mock_processor
    )

    query = SearchQuery(query="вопрос", scrape_top_n=0)
    response = await service.ask(query)

    # при низком скоре и отсутствии виннеров должен быть фолбек
    assert "Инфы мало" in response.answer or "сорян" in response.answer
