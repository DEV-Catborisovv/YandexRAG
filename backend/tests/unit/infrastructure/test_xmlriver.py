import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from src.infrastructure.clients.xmlriver import XMLRiverClient
from src.domain.exceptions import ExternalAPIException

@pytest.mark.asyncio
async def test_xmlriver_search_success():
    client = XMLRiverClient(user_id="u", api_key="k")
    
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = "<root><doc><title>T</title></doc></root>"
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient.get", return_value=mock_response):
        results = await client.search("query")
        assert len(results) == 1
        assert results[0]["title"] == "T"

@pytest.mark.asyncio
async def test_xmlriver_api_error():
    client = XMLRiverClient(user_id="u", api_key="k")
    
    mock_response = AsyncMock()
    mock_response.status_code = 403
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("Err", request=MagicMock(), response=mock_response)
    
    with patch("httpx.AsyncClient.get", return_value=mock_response):
        with pytest.raises(ExternalAPIException):
            await client.search("query")
