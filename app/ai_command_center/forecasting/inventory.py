from __future__ import annotations


def inventory_purchase_recommendation(current_stock: float, forecast_demand: float, safety_stock: float, lead_time_days: float = 1.0) -> dict:
    if current_stock is None or forecast_demand is None:
        return {"status": "INSUFFICIENT_DATA", "message": "Inventory and demand data required for purchase recommendations."}
    need = (forecast_demand + safety_stock) - current_stock
    recommended = max(0, round(need + (forecast_demand * lead_time_days * 0.25), 0))
    return {
        "recommended_purchase_quantity": int(recommended),
        "forecast_demand": float(forecast_demand),
        "safety_stock": float(safety_stock),
        "lead_time_days": float(lead_time_days),
    }
