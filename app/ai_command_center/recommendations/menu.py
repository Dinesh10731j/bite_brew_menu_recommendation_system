from __future__ import annotations


def menu_recommendation(item: str, margin: float, demand: float) -> dict:
    if demand <= 0 or margin <= 0:
        return {"status": "INSUFFICIENT_DATA", "message": "Menu financing metrics are not available."}
    return {
        "item": item,
        "classification": "STAR" if demand > 15 and margin > 0.3 else "VOLUME_DRIVER" if demand > 15 else "HIDDEN_GEM" if margin > 0.35 else "PROBLEM_ITEM",
        "reason": "High demand and healthy margin.",
    }
