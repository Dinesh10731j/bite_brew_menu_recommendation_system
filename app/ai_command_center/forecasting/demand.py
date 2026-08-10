from __future__ import annotations

from statistics import mean
from typing import Iterable, List


def item_demand_forecast(history: Iterable[float], current_demand: float | None = None) -> dict:
    series = [float(v) for v in history]
    if len(series) < 2:
        return {"status": "INSUFFICIENT_DATA", "message": "No enough historical demand data available."}
    avg = mean(series)
    next_demand = avg * 1.1
    change = ((next_demand - (current_demand or avg)) / (current_demand or avg)) * 100 if (current_demand or avg) else 0.0
    return {
        "current_demand": float(current_demand or avg),
        "expected_demand": round(next_demand, 2),
        "demand_change_percent": round(change, 2),
        "confidence": 0.72,
    }
