from __future__ import annotations


def evaluate_revenue_leakage(expected_revenue: float, recorded_revenue: float, discounts: float = 0.0, refunds: float = 0.0, voids: float = 0.0) -> dict:
    difference = float(expected_revenue) - float(recorded_revenue)
    percentage = (difference / float(expected_revenue)) * 100 if expected_revenue else 0.0
    possible = []
    if discounts > 0:
        possible.append("Excessive discounts")
    if refunds > 0:
        possible.append("Refund activity")
    if voids > 0:
        possible.append("Voided orders")
    if delta := abs(difference):
        if delta > 0:
            possible.append("Payment reconciliation mismatch")
    if not possible:
        possible = ["No material leakage detected."]
    if percentage >= 10:
        risk_level = "HIGH"
    elif percentage >= 5:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"
    return {
        "risk_level": risk_level,
        "expected_revenue": float(expected_revenue),
        "recorded_revenue": float(recorded_revenue),
        "difference": float(difference),
        "difference_percentage": round(percentage, 2),
        "possible_causes": possible,
    }
