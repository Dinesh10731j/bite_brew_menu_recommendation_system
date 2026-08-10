from __future__ import annotations


def purchasing_recommendation(current_stock: float, forecast_demand: float, safety_stock: float, lead_time_days: float = 1.0) -> dict:
    if current_stock is None or forecast_demand is None:
        return {"status": "INSUFFICIENT_DATA", "message": "Inventory and lead-time inputs are missing."}
    quantity = max(0, round((forecast_demand + safety_stock + (forecast_demand * lead_time_days * 0.25)) - current_stock, 0))
    return {"recommended_purchase_quantity": int(quantity), "reason": "Forecast demand plus safety stock exceeds current inventory."}
