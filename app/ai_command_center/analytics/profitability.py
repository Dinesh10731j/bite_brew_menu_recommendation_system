from __future__ import annotations


def calculate_profit_margin(selling_price: float, ingredient_cost: float, packaging_cost: float = 0.0, discount_cost: float = 0.0) -> dict:
    if selling_price is None or ingredient_cost is None:
        return {"status": "INSUFFICIENT_DATA", "message": "Menu pricing and ingredient cost are required."}
    net_price = max(0.0, float(selling_price) - float(discount_cost))
    gross_profit = net_price - float(ingredient_cost) - float(packaging_cost)
    margin = (gross_profit / net_price) * 100 if net_price else 0.0
    return {
        "selling_price": float(selling_price),
        "ingredient_cost": float(ingredient_cost),
        "packaging_cost": float(packaging_cost),
        "discount_cost": float(discount_cost),
        "estimated_profit": round(gross_profit, 2),
        "profit_margin": round(margin, 2),
    }
