import pytest
from fastapi.testclient import TestClient
from src.app import app
from src.api.dependencies import get_rag_service
from src.application.rag_service import RAGService
from src.domain.models import RAGResponse, SearchResult
from unittest.mock import AsyncMock

# тесты апишки
# мокаем раг сервис шоб не ходить в сеть

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_rag_service():
    mock = AsyncMock(spec=RAGService)
    mock.ask.return_value = RAGResponse(
        answer="Тестовый ответ",
        sources=[SearchResult(title="Т", url="U", snippet="S", score=1.0)]
    )
    return mock

def test_root_endpoint(client):
    # проверяем шо главная работает
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_ask_endpoint(client, mock_rag_service):
    # подменяем сервис на мок
    app.dependency_overrides[get_rag_service] = lambda: mock_rag_service
    
    response = client.post("/api/v1/search/", json={"query": "привет"})
    assert response.status_code == 200
    assert response.json()["answer"] == "Тестовый ответ"
    
    app.dependency_overrides.clear()
