from __future__ import annotations

from typing import Any


def clamp_confidence(value: Any, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(maximum, numeric))


def confidence_label(confidence: float) -> str:
    if confidence >= 0.9:
        return "VERY_HIGH"
    if confidence >= 0.75:
        return "HIGH"
    if confidence >= 0.5:
        return "MODERATE"
    return "LOW"


def score_confidence(sample_size: int, volatility: float = 0.0) -> float:
    if sample_size <= 0:
        return 0.0
    strength = min(0.95, 0.35 + (sample_size / 200.0))
    stability = max(0.0, 1.0 - volatility)
    return round(max(0.0, min(0.99, strength * stability)), 3)
