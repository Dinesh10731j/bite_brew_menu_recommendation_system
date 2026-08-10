from __future__ import annotations


def stockout_risk(current_stock: float, average_daily_usage: float, lead_time_days: float = 1.0) -> dict:
    if current_stock is None or average_daily_usage in (None, 0):
        return {"status": "INSUFFICIENT_DATA", "message": "Inventory data is incomplete."}
    days = current_stock / average_daily_usage if average_daily_usage else 0.0
    if days <= 2:
        risk = "HIGH"
    elif days <= 5:
        risk = "MEDIUM"
    else:
        risk = "LOW"
    recommended = max(0, round((average_daily_usage * (lead_time_days + 1)) - current_stock, 0))
    return {"stockout_risk": risk, "days_until_stockout": round(days, 2), "recommended_purchase": int(recommended)}
