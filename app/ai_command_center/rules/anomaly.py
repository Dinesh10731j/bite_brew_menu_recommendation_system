from __future__ import annotations

from statistics import mean, pstdev
from typing import Iterable, List


def zscore_anomaly(values: Iterable[float], threshold: float = 2.5) -> List[float]:
    series = [float(value) for value in values]
    if len(series) < 3:
        return []
    avg = mean(series)
    sigma = pstdev(series)
    if sigma == 0:
        return []
    return [value for value in series if abs((value - avg) / sigma) >= threshold]
