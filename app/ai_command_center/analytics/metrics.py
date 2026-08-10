from __future__ import annotations

from statistics import mean


def average_order_value(revenues: list[float], order_counts: list[int]) -> dict:
    if not revenues or not order_counts:
        return {"status": "INSUFFICIENT_DATA", "message": "No order or revenue totals available."}
    revenue_total = sum(revenues)
    order_total = sum(order_counts)
    if order_total <= 0:
        return {"status": "INSUFFICIENT_DATA", "message": "No valid order volume found."}
    return {"average_order_value": round(revenue_total / order_total, 2), "revenue_total": round(revenue_total, 2), "order_total": order_total}
