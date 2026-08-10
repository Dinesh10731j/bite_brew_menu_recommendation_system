from __future__ import annotations


def operational_health(order_volume: float, refunds: float, voids: float, cancellations: float, staffing_gap: float = 0.0) -> dict:
    score = 100.0
    if order_volume <= 0:
        return {"status": "INSUFFICIENT_DATA", "message": "Order data is unavailable."}
    score -= min(30, refunds * 2)
    score -= min(30, voids * 3)
    score -= min(25, cancellations * 2)
    score -= min(20, staffing_gap * 5)
    score = max(0.0, score)
    return {"score": round(score, 1), "status": "HEALTHY" if score >= 80 else "WATCH" if score >= 60 else "RISK"}
