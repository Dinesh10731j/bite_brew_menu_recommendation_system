import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint redirect metadata."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "Bite & Brew AI Recommendation Service"
    assert "docs" in data
    assert "health" in data


@pytest.mark.asyncio
async def test_health_check_endpoint(client: AsyncClient):
    """Test /api/v1/health readiness probe."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "environment" in data
    assert "database_connected" in data
    assert "embedding_model_loaded" in data
    assert "timestamp" in data
    assert data["embedding_model_loaded"] is True
