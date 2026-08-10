from __future__ import annotations

from statistics import mean
from typing import Iterable, List


def moving_average_forecast(values: Iterable[float], days: int = 7) -> dict:
    series = [float(v) for v in values]
    if len(series) < 2:
        return {"status": "INSUFFICIENT_DATA", "message": "Not enough historical values to forecast sales."}
    average = mean(series[-days:]) if len(series) >= days else mean(series)
    lower = average * 0.9
    upper = average * 1.1
    return {
        "forecast": {f"next_{days}_days": round(average * days, 2)},
        "lower_bound": round(lower * days, 2),
        "upper_bound": round(upper * days, 2),
        "confidence": 0.75,
    }
