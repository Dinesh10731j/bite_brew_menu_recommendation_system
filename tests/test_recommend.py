import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_recommendation_success(client: AsyncClient):
    """Test successful recommendation endpoint response structure."""
    payload = {
        "user_craving": "I want something spicy and cheesy for lunch",
        "max_price": 25.00,
        "category": "Veg",
        "top_n": 3,
    }
    response = await client.post("/api/v1/recommend", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["query_craving"] == payload["user_craving"]
    assert data["filters_applied"]["max_price"] == 25.00
    assert data["filters_applied"]["category"] == "Veg"
    assert isinstance(data["recommendations"], list)
    assert len(data["recommendations"]) <= 3

    if data["recommendations"]:
        first = data["recommendations"][0]
        assert "id" in first
        assert "name" in first
        assert "description" in first
        assert "price" in first
        assert "is_vegetarian" in first
        assert "match_score" in first
        assert "distance" in first


@pytest.mark.asyncio
async def test_recommendation_category_filter(client: AsyncClient):
    """Test category name filter constraint."""
    payload = {
        "user_craving": "burger and fries",
        "category": "Veg",
        "top_n": 5,
    }
    response = await client.post("/api/v1/recommend", json=payload)
    assert response.status_code == 200
    data = response.json()
    for rec in data["recommendations"]:
        category = rec.get("category")
        if isinstance(category, dict):
            assert category.get("name") is not None
        else:
            assert category is not None


@pytest.mark.asyncio
async def test_recommendation_price_filter(client: AsyncClient):
    """Test maximum price filter constraint."""
    payload = {
        "user_craving": "cold beverage coffee",
        "max_price": 10.00,
        "top_n": 5,
    }
    response = await client.post("/api/v1/recommend", json=payload)
    assert response.status_code == 200
    data = response.json()
    for rec in data["recommendations"]:
        assert rec["price"] <= 10.00


@pytest.mark.asyncio
async def test_recommendation_invalid_craving(client: AsyncClient):
    """Test 422 Unprocessable Entity on empty craving string."""
    payload = {
        "user_craving": "   ",
        "top_n": 3,
    }
    response = await client.post("/api/v1/recommend", json=payload)
    assert response.status_code == 422
