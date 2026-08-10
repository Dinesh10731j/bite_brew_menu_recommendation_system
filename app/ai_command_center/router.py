from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.ai_command_center.service import AICommandCenterService
from app.api.deps import get_db_connection_dep, verify_api_key
from app.core.redis import get_cached_response, set_cached_response

router = APIRouter(prefix="/api/ai", tags=["AI Command Center"])


async def get_command_center_service(
    db_conn=Depends(get_db_connection_dep),
    _api_key: str | None = Depends(verify_api_key),
) -> AICommandCenterService:
    return AICommandCenterService(conn=db_conn)


@router.get("/command-center", summary="AI operations command center", status_code=status.HTTP_200_OK)
async def command_center(
    request: Request,
    service: AICommandCenterService = Depends(get_command_center_service),
) -> Dict[str, Any]:
    try:
        cache_key = "ai:command-center:dashboard"
        cached = await get_cached_response(cache_key)
        if cached:
            return cached
        payload = await service.get_command_center_payload()
        await set_cached_response(cache_key, payload, ttl=300)
        return payload
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/health-score", summary="AI operational health score")
async def health_score(service: AICommandCenterService = Depends(get_command_center_service)) -> Dict[str, Any]:
    return await service.get_health_score()


@router.get("/anomalies", summary="AI anomaly detection results")
async def anomalies(service: AICommandCenterService = Depends(get_command_center_service)) -> Dict[str, Any]:
    return {"anomalies": await service.get_anomalies()}


@router.get("/revenue-leakage", summary="Revenue leakage and reconciliation analysis")
async def revenue_leakage(service: AICommandCenterService = Depends(get_command_center_service)) -> Dict[str, Any]:
    return await service.get_revenue_leakage()


@router.get("/inventory-risks", summary="Inventory stockout and purchasing recommendations")
async def inventory_risks(service: AICommandCenterService = Depends(get_command_center_service)) -> Dict[str, Any]:
    return {"inventory": await service.get_inventory_risks()}


@router.get("/waste-analysis", summary="Waste and preparation analysis")
async def waste_analysis(service: AICommandCenterService = Depends(get_command_center_service)) -> Dict[str, Any]:
    return await service.get_waste_analysis()


@router.get("/sales-forecast", summary="Operational sales forecast")
async def sales_forecast(service: AICommandCenterService = Depends(get_command_center_service)) -> Dict[str, Any]:
    return await service.get_sales_forecast()


@router.get("/demand-forecast", summary="Demand forecast")
async def demand_forecast(service: AICommandCenterService = Depends(get_command_center_service)) -> Dict[str, Any]:
    return {"status": "INSUFFICIENT_DATA", "message": "Demand forecast requires item-level historical sales data."}


@router.get("/menu-insights", summary="Menu profitability and recommendation insights")
async def menu_insights(service: AICommandCenterService = Depends(get_command_center_service)) -> Dict[str, Any]:
    return {"stars": [{"item": "Chicken MoMo", "classification": "STAR"}], "hidden_gems": [], "problem_items": []}


@router.get("/staff-forecast", summary="Staffing demand forecast")
async def staff_forecast(service: AICommandCenterService = Depends(get_command_center_service)) -> Dict[str, Any]:
    return {"status": "STAFFING_DATA_UNAVAILABLE", "message": "Staffing data is not available in the current database."}


@router.get("/customer-insights", summary="Customer retention and churn intelligence")
async def customer_insights(service: AICommandCenterService = Depends(get_command_center_service)) -> Dict[str, Any]:
    return {"status": "INSUFFICIENT_DATA", "message": "Customer transaction history is required for retention and churn analysis."}


@router.get("/recommendations", summary="AI recommendations")
async def recommendations(service: AICommandCenterService = Depends(get_command_center_service)) -> Dict[str, Any]:
    return {"recommendations": await service.get_recommendations()}


@router.get("/daily-summary", summary="Daily operational summary")
async def daily_summary(service: AICommandCenterService = Depends(get_command_center_service)) -> Dict[str, Any]:
    return await service.get_daily_summary()


@router.post("/recommendations/{recommendation_id}/acknowledge", summary="Acknowledge an AI recommendation")
async def acknowledge_recommendation(
    recommendation_id: str,
    service: AICommandCenterService = Depends(get_command_center_service),
) -> Dict[str, Any]:
    return {"recommendation_id": recommendation_id, "status": "ACKNOWLEDGED"}


@router.post("/recommendations/{recommendation_id}/resolve", summary="Resolve an AI recommendation")
async def resolve_recommendation(
    recommendation_id: str,
    service: AICommandCenterService = Depends(get_command_center_service),
) -> Dict[str, Any]:
    return {"recommendation_id": recommendation_id, "status": "RESOLVED"}


@router.post("/recommendations/{recommendation_id}/dismiss", summary="Dismiss an AI recommendation")
async def dismiss_recommendation(
    recommendation_id: str,
    service: AICommandCenterService = Depends(get_command_center_service),
) -> Dict[str, Any]:
    return {"recommendation_id": recommendation_id, "status": "DISMISSED"}
