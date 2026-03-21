import pytest
from unittest.mock import MagicMock, patch
from src.infrastructure.clients.embeddings import YandexEmbeddingsClient
from src.domain.exceptions import ExternalAPIException

@pytest.mark.asyncio
async def test_embeddings_success():
    with patch("src.infrastructure.clients.embeddings.YCloudML") as mock_sdk_class:
        mock_sdk = mock_sdk_class.return_value
        mock_model = MagicMock()
        mock_sdk.models.text_embeddings.return_value = mock_model
        
        mock_result = MagicMock()
        mock_result.embedding = [0.1, 0.2, 0.3]
        mock_model.run.return_value = mock_result
        
        client = YandexEmbeddingsClient(folder_id="f", api_key="k")
        embs = await client.get_embeddings(["test"])
        
        assert len(embs) == 1
        assert embs[0] == [0.1, 0.2, 0.3]

@pytest.mark.asyncio
async def test_query_embedding(monkeypatch):
    with patch("src.infrastructure.clients.embeddings.YCloudML") as mock_sdk_class:
        mock_sdk = mock_sdk_class.return_value
        mock_model = MagicMock()
        mock_sdk.models.text_embeddings.return_value = mock_model
        
        result = MagicMock()
        result.embedding = [0.5] * 256
        mock_model.run.return_value = result
        
        client = YandexEmbeddingsClient(folder_id="f", api_key="k")
        emb = await client.get_query_embedding("query")
        assert len(emb) == 256
