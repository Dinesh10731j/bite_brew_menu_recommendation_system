from __future__ import annotations


def staffing_recommendation(expected_orders: float, current_staffing: float) -> dict:
    if expected_orders <= 0:
        return {"status": "STAFFING_DATA_UNAVAILABLE", "message": "No staffing demand data is available."}
    recommended = max(1, int(round(expected_orders / 20)))
    return {"expected_orders": float(expected_orders), "current_staffing": float(current_staffing), "recommended_staffing": recommended}
