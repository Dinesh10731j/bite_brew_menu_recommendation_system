from __future__ import annotations


def waste_analysis(prepared_quantity: float, sold_quantity: float, unit_cost: float = 0.0) -> dict:
    prepared = float(prepared_quantity)
    sold = float(sold_quantity)
    waste = max(0.0, prepared - sold)
    waste_rate = (waste / prepared * 100) if prepared else 0.0
    cost = waste * float(unit_cost)
    return {
        "waste": round(waste, 2),
        "waste_rate": round(waste_rate, 2),
        "waste_cost": round(cost, 2),
        "waste_trend": "UP" if waste_rate > 20 else "STABLE",
    }
