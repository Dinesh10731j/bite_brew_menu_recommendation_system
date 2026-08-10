from __future__ import annotations


def customer_insights(repeat_customers: int = 0, inactive_customers: int = 0, high_value_customers: int = 0) -> dict:
    return {
        "repeat_customers": repeat_customers,
        "inactive_customers": inactive_customers,
        "high_value_customers": high_value_customers,
        "churn_risk": "LOW" if inactive_customers <= 5 else "MEDIUM" if inactive_customers <= 15 else "HIGH",
    }
