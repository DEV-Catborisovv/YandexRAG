import pytest
from unittest.mock import MagicMock, patch
from src.infrastructure.clients.yandex_gpt import YandexGPTClient
from src.domain.exceptions import ExternalAPIException

# тесты для яндекс гпт
# мокаем sdk шоб бабки не тратить

@pytest.mark.asyncio
async def test_yandex_gpt_success():
    with patch("src.infrastructure.clients.yandex_gpt.YCloudML") as mock_sdk_class:
        mock_sdk = mock_sdk_class.return_value
        mock_model = MagicMock()
        mock_sdk.models.completions.return_value = mock_model
        
        mock_result = MagicMock()
        mock_result.alternatives = [MagicMock(text="Привет, я нейросеть")]
        mock_model.run.return_value = mock_result
        
        client = YandexGPTClient(folder_id="f", api_key="k")
        answer = await client.generate_answer("Привет")
        
        assert answer == "Привет, я нейросеть"
        mock_sdk.models.completions.assert_called_once()


@pytest.mark.asyncio
async def test_yandex_gpt_score_success():
    with patch("src.infrastructure.clients.yandex_gpt.YCloudML") as mock_sdk_class:
        mock_sdk = mock_sdk_class.return_value
        mock_model = MagicMock()
        mock_sdk.models.completions.return_value = mock_model
        
        mock_result = MagicMock()
        # имитируем ответ с цифрой
        mock_result.alternatives = [MagicMock(text="Оценка: 9")]
        mock_model.run.return_value = mock_result
        
        client = YandexGPTClient(folder_id="f", api_key="k")
        score = await client.score_passage("как дела", "все хорошо")
        
        assert score == 9


@pytest.mark.asyncio
async def test_yandex_gpt_select_winners():
    with patch("src.infrastructure.clients.yandex_gpt.YCloudML") as mock_sdk_class:
        mock_sdk = mock_sdk_class.return_value
        mock_model = MagicMock()
        mock_sdk.models.completions.return_value = mock_model
        
        mock_result = MagicMock()
        mock_result.alternatives = [MagicMock(text="0, 2, 1")]
        mock_model.run.return_value = mock_result
        
        client = YandexGPTClient(folder_id="f", api_key="k")
        from src.domain.models import SearchResult
        candidates = [
            SearchResult(title="Статья 1", url="u1", snippet="с1"), # 0
            SearchResult(title="Статья 2", url="u2", snippet="с2"), # 1
            SearchResult(title="Статья 3", url="u3", snippet="с3")  # 2
        ]
        winners = await client.select_winners("запрос", candidates)
        
        assert len(winners) == 3
        # порядок должен быть 0, 2, 1
        assert winners[0].title == "Статья 1"
        assert winners[1].title == "Статья 3"
        assert winners[2].title == "Статья 2"
