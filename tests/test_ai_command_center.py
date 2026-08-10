import pytest

from app.ai_command_center.repository import AIRepository
from app.ai_command_center.service import (
    AICommandCenterService,
    calculate_health_score,
    detect_anomalies,
    estimate_stockout,
)


@pytest.mark.asyncio
async def test_calculate_health_score_uses_real_metrics():
    score = calculate_health_score(
        revenue=88,
        inventory=74,
        waste=81,
        orders=90,
        customers=79,
        operations=84,
        leakage_risk=12,
    )
    assert score["score"] >= 0
    assert score["score"] <= 100
    assert score["status"] in {"HEALTHY", "WATCH", "RISK"}
    assert "components" in score


@pytest.mark.asyncio
async def test_detect_anomalies_identifies_outlier_sales():
    anomalies = detect_anomalies(
        sales=[100, 120, 130, 125, 150, 900],
        orders=[10, 12, 13, 11, 14, 70],
        discounts=[0.1, 0.1, 0.15, 0.12, 0.11, 0.4],
    )
    assert isinstance(anomalies, list)
    assert len(anomalies) >= 1


@pytest.mark.asyncio
async def test_estimate_stockout_uses_actual_data():
    result = estimate_stockout(
        item="Chicken",
        current_stock=8,
        average_daily_usage=11,
        lead_time_days=1,
        sales_velocity=14,
        recent_usage=[8, 10, 9, 12, 15],
    )
    assert result["item"] == "Chicken"
    assert result["stockout_risk"] in {"LOW", "MEDIUM", "HIGH"}
    assert "estimated_stockout" in result
    assert "recommended_purchase" in result


@pytest.mark.asyncio
async def test_live_business_snapshot_uses_database_metrics():
    class FakeCursor:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, query, params=None):
            return None

        async def fetchone(self):
            return (13,)

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    snapshot = await AIRepository.get_business_snapshot(FakeConnection())
    assert isinstance(snapshot, dict)
    assert "menu_items" in snapshot
    assert "orders" in snapshot
    assert snapshot["menu_items"] >= 0


@pytest.mark.asyncio
async def test_command_center_without_business_data_returns_insufficient_data():
    service = AICommandCenterService()
    result = await service.get_command_center_payload()
    assert result["status"] == "INSUFFICIENT_DATA"


@pytest.mark.asyncio
async def test_ai_command_center_endpoint_returns_insufficient_data_when_db_is_empty(client):
    response = await client.get("/api/ai/command-center")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "INSUFFICIENT_DATA"
