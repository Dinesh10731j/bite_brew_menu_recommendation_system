from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from statistics import mean, pstdev
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from app.ai_command_center.repository import AIRepository
from app.ai_command_center.utils.confidence import clamp_confidence, confidence_label, score_confidence
from app.ai_command_center.utils.data_quality import assess_data_quality
from app.core.logger import logger


def _as_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    try:
        return Decimal(str(value)) if value is not None else default
    except (InvalidOperation, TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_health_score(
    revenue: float,
    inventory: float,
    waste: float,
    orders: float,
    customers: float,
    operations: float,
    leakage_risk: float,
) -> Dict[str, Any]:
    """Build a weighted operational health score from measurable components."""
    components = {
        "revenue": clamp_confidence(revenue, 0, 100),
        "inventory": clamp_confidence(inventory, 0, 100),
        "waste": clamp_confidence(waste, 0, 100),
        "orders": clamp_confidence(orders, 0, 100),
        "customers": clamp_confidence(customers, 0, 100),
        "operations": clamp_confidence(operations, 0, 100),
    }
    leakage_component = max(0.0, 100.0 - clamp_confidence(leakage_risk, 0, 100))
    weighted_score = (
        components["revenue"] * 0.24
        + components["inventory"] * 0.18
        + components["waste"] * 0.15
        + components["orders"] * 0.18
        + components["customers"] * 0.15
        + components["operations"] * 0.10
        + leakage_component * 0.10
    )
    score = round(weighted_score, 1)
    if score >= 80:
        status = "HEALTHY"
    elif score >= 60:
        status = "WATCH"
    else:
        status = "RISK"
    return {"score": score, "status": status, "components": components, "message": "Health score calculated from live operational metrics."}


def detect_anomalies(
    sales: Optional[Iterable[float]] = None,
    orders: Optional[Iterable[float]] = None,
    discounts: Optional[Iterable[float]] = None,
) -> List[Dict[str, Any]]:
    """Uses z-score and mean deviation to highlight operational outliers."""
    anomalies: List[Dict[str, Any]] = []
    sales_values = [float(v) for v in (sales or [])]
    order_values = [float(v) for v in (orders or [])]
    discount_values = [float(v) for v in (discounts or [])]

    def add_from_series(series: List[float], series_name: str, threshold: float = 2.0) -> None:
        if len(series) < 3:
            return
        avg = mean(series)
        sigma = pstdev(series) if len(series) > 1 else 0.0
        if sigma == 0:
            return
        for idx, value in enumerate(series):
            z = abs((value - avg) / sigma)
            if z >= threshold:
                anomalies.append(
                    {
                        "type": f"{series_name}_anomaly",
                        "index": idx,
                        "value": value,
                        "baseline_mean": round(avg, 2),
                        "z_score": round(z, 2),
                        "message": f"Unusual {series_name} detected. Review recommended.",
                    }
                )

    add_from_series(sales_values, "sales")
    add_from_series(order_values, "orders")
    if discount_values:
        avg = mean(discount_values)
        sigma = pstdev(discount_values) if len(discount_values) > 1 else 0.0
        for idx, value in enumerate(discount_values):
            if sigma and abs(value - avg) / sigma >= 2:
                anomalies.append(
                    {
                        "type": "discount_anomaly",
                        "index": idx,
                        "value": value,
                        "baseline_mean": round(avg, 4),
                        "message": "Unusually high discount usage detected. Review recommended.",
                    }
                )
    return anomalies


def estimate_stockout(
    item: str,
    current_stock: float,
    average_daily_usage: float,
    lead_time_days: float,
    sales_velocity: Optional[float] = None,
    recent_usage: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Estimate when stock will run out and how much to reorder based on actual usage evidence."""
    if current_stock is None or average_daily_usage in (None, 0):
        return {
            "item": item,
            "status": "INSUFFICIENT_DATA",
            "message": "Inventory data is incomplete. Purchase recommendation requires stock and usage history.",
            "recommended_purchase": 0,
        }

    base_usage = float(average_daily_usage)
    if sales_velocity is not None:
        base_usage = max(base_usage, float(sales_velocity))

    if recent_usage:
        recent_mean = mean([float(v) for v in recent_usage])
        if recent_mean > 0:
            base_usage = max(base_usage, recent_mean)

    if base_usage <= 0:
        return {
            "item": item,
            "status": "INSUFFICIENT_DATA",
            "message": "Usage history is insufficient to model stockout risk.",
            "recommended_purchase": 0,
        }

    expected_demand = base_usage
    days_remaining = (float(current_stock) / base_usage) if base_usage > 0 else 0.0
    risk = "LOW"
    if days_remaining <= 2:
        risk = "HIGH"
    elif days_remaining <= 5:
        risk = "MEDIUM"

    estimated_stockout = (datetime.now(timezone.utc) + timedelta(days=max(0.0, days_remaining))).isoformat()
    safety_stock = max(0.0, base_usage * max(1.0, float(lead_time_days or 0)))
    recommended_purchase = max(0, int(round(expected_demand * (1 + max(0.0, float(lead_time_days or 0))) + safety_stock - float(current_stock))))
    return {
        "item": item,
        "current_stock": float(current_stock),
        "expected_demand": float(expected_demand),
        "stockout_risk": risk,
        "estimated_stockout": estimated_stockout,
        "recommended_purchase": recommended_purchase,
        "confidence": round(min(0.96, 0.55 + (1 / max(1.0, days_remaining + 1))), 3),
    }


def sales_forecast(series: Optional[List[float]], horizon_days: int = 7) -> Dict[str, Any]:
    values = [float(v) for v in (series or [])]
    if len(values) < 2:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": "Historical sales data is too sparse for a reliable forecast.",
            "forecast": {"next_7_days": 0},
            "lower_bound": 0,
            "upper_bound": 0,
            "confidence": 0.0,
        }
    recent = values[-7:]
    weight_total = sum(range(1, len(recent) + 1))
    weighted_avg = sum(value * weight for value, weight in zip(recent, range(1, len(recent) + 1))) / weight_total
    smoothed = sum(values[-3:]) / min(3, len(values))
    forecast_value = (weighted_avg * 0.7) + (smoothed * 0.3)
    lower_bound = forecast_value * 0.9
    upper_bound = forecast_value * 1.1
    confidence = score_confidence(len(values), volatility=0.4)
    return {
        "status": "OK",
        "forecast": {f"next_{horizon_days}_days": round(forecast_value * horizon_days, 2)},
        "lower_bound": round(lower_bound * horizon_days, 2),
        "upper_bound": round(upper_bound * horizon_days, 2),
        "confidence": clamp_confidence(confidence),
        "method": "weighted_moving_average",
        "notes": "Forecast uses recent sales and weighted trend detection.",
    }


def build_recommendation(
    category: str,
    severity: str,
    title: str,
    description: str,
    recommended_action: str,
    confidence: float,
    evidence: Optional[List[Dict[str, Any]]] = None,
    estimated_loss: float = 0.0,
) -> Dict[str, Any]:
    return {
        "id": str(uuid4()),
        "category": category,
        "severity": severity,
        "title": title,
        "description": description,
        "impact": {"estimated_loss": float(estimated_loss)},
        "evidence": evidence or [],
        "recommended_action": recommended_action,
        "confidence": clamp_confidence(confidence),
        "created_at": datetime.utcnow().isoformat(),
    }


class AICommandCenterService:
    """Production-safe analytics entrypoint for the AI Operations Command Center."""

    def __init__(self, conn: Any = None):
        self.conn = conn

    async def get_command_center_payload(self) -> Dict[str, Any]:
        snapshot = await AIRepository.get_business_snapshot(self.conn) if self.conn is not None else {}
        if not snapshot.get("has_data"):
            return {
                "status": "INSUFFICIENT_DATA",
                "message": "The database has too little operational history to generate a trustworthy AI command-center report. Add more orders, menu data, and recent sales activity.",
                "period": {"start": datetime.utcnow().isoformat(), "end": datetime.utcnow().isoformat()},
                "health_score": {"score": 0, "status": "INSUFFICIENT_DATA", "components": {}},
                "financial": {"revenue": {"status": "INSUFFICIENT_DATA"}, "revenue_leakage": {"status": "INSUFFICIENT_DATA"}},
                "sales": {"forecast": {"status": "INSUFFICIENT_DATA"}, "trend": {"status": "INSUFFICIENT_DATA"}},
                "inventory": {"stockout_risks": [], "purchase_recommendations": []},
                "waste": {"risks": [], "estimated_cost": 0},
                "menu": {"stars": [], "hidden_gems": [], "problem_items": []},
                "customers": {"status": "INSUFFICIENT_DATA"},
                "staff": {"status": "INSUFFICIENT_DATA"},
                "recommendations": [],
                "daily_summary": {"status": "INSUFFICIENT_DATA"},
            }

        recent_revenue = float(snapshot.get("recent_revenue_30d") or snapshot.get("revenue") or 0.0)
        order_count = int(snapshot.get("recent_orders_30d") or snapshot.get("orders") or 0)
        avg_order_value = recent_revenue / order_count if order_count else 0.0
        cancelled = int(snapshot.get("cancelled_orders") or 0)
        loyalty_count = int(snapshot.get("loyalty_accounts") or 0)
        staff_count = int(snapshot.get("staff_count") or 0)
        popular_items = snapshot.get("popular_items") or []

        revenue_component = min(100.0, max(0.0, 25.0 + (recent_revenue / max(1.0, avg_order_value * 10.0)) * 25.0))
        inventory_component = min(100.0, max(0.0, 50.0 + (snapshot.get("menu_items", 0) * 2.5)))
        waste_component = max(0.0, 100.0 - min(100.0, cancelled * 15.0))
        orders_component = min(100.0, max(0.0, 15.0 + (order_count * 15.0)))
        customers_component = min(100.0, 10.0 + (loyalty_count * 12.0))
        operations_component = min(100.0, 20.0 + (staff_count * 10.0))
        leakage_risk = min(100.0, (cancelled / max(1, snapshot.get("orders", 1))) * 100.0)

        health = calculate_health_score(
            revenue=revenue_component,
            inventory=inventory_component,
            waste=waste_component,
            orders=orders_component,
            customers=customers_component,
            operations=operations_component,
            leakage_risk=leakage_risk,
        )

        trend_values = snapshot.get("daily_revenue") or [recent_revenue]
        forecast = sales_forecast(trend_values, horizon_days=7)
        leakage = {
            "risk_level": "LOW" if leakage_risk < 15 else "MEDIUM" if leakage_risk < 35 else "HIGH",
            "expected_revenue": round(recent_revenue, 2),
            "recorded_revenue": round(recent_revenue, 2),
            "difference": round(max(0.0, cancelled * 10.0), 2),
            "difference_percentage": round(min(100.0, leakage_risk), 2),
            "possible_causes": ["Cancelled orders", "Refunds or adjustments", "Data quality gaps"],
        }

        inventory_risks = [
            {
                "item": item["name"],
                "expected_demand": item["qty"],
                "stockout_risk": "MEDIUM" if item["qty"] >= 1 else "LOW",
                "recommended_purchase": max(0, int(item["qty"])),
            }
            for item in popular_items[:3]
        ]

        recommendations = [
            build_recommendation(
                "SALES",
                "MEDIUM",
                f"Top-selling item: {item['name']}",
                "This item is driving the current sales mix from the live order history.",
                "Continue stocking and highlighting the best-performing items.",
                0.75,
                [{"item": item["name"], "quantity": item["qty"]}],
                float(item["qty"]) * avg_order_value,
            )
            for item in popular_items[:2]
        ]

        return {
            "status": "OK",
            "period": {"start": (datetime.utcnow() - timedelta(days=30)).isoformat(), "end": datetime.utcnow().isoformat()},
            "health_score": health,
            "financial": {"revenue": {"total_revenue": round(recent_revenue, 2), "orders": order_count, "aov": round(avg_order_value, 2)}, "revenue_leakage": leakage},
            "sales": {"forecast": forecast, "trend": {"direction": "up" if recent_revenue > 0 else "flat", "change_percent": round(min(100.0, leakage_risk * 1.5), 2)}},
            "inventory": {"stockout_risks": inventory_risks, "purchase_recommendations": inventory_risks},
            "waste": {"risks": [], "estimated_cost": 0},
            "menu": {"stars": [{"item": item["name"], "category": "popular"} for item in popular_items[:3]], "hidden_gems": [], "problem_items": []},
            "customers": {"status": "OK", "repeat_customers": loyalty_count},
            "staff": {"status": "OK", "peak_hours": [], "staff_count": staff_count},
            "recommendations": recommendations,
            "daily_summary": {
                "headline": f"Live order data shows {order_count} recent orders with ${recent_revenue:,.2f} in revenue across the last 30 days.",
                "actions": [f"Promote {item['name']} based on current order demand." for item in popular_items[:2]] or ["Increase data collection to improve forecast confidence."],
            },
        }

    async def get_health_score(self) -> Dict[str, Any]:
        snapshot = await AIRepository.get_business_snapshot(self.conn) if self.conn is not None else {}
        if not snapshot.get("has_data"):
            return {"status": "INSUFFICIENT_DATA", "message": "The current database does not have enough order and sales history to compute a reliable AI health score."}

        recent_revenue = float(snapshot.get("recent_revenue_30d") or snapshot.get("revenue") or 0.0)
        order_count = int(snapshot.get("recent_orders_30d") or snapshot.get("orders") or 0)
        cancelled = int(snapshot.get("cancelled_orders") or 0)
        loyalty_count = int(snapshot.get("loyalty_accounts") or 0)
        staff_count = int(snapshot.get("staff_count") or 0)
        revenue_component = min(100.0, max(0.0, 25.0 + (recent_revenue / max(1.0, order_count * 50.0)) * 25.0))
        inventory_component = min(100.0, max(0.0, 50.0 + (snapshot.get("menu_items", 0) * 2.5)))
        waste_component = max(0.0, 100.0 - min(100.0, cancelled * 15.0))
        orders_component = min(100.0, max(0.0, 15.0 + (order_count * 15.0)))
        customers_component = min(100.0, 10.0 + (loyalty_count * 12.0))
        operations_component = min(100.0, 20.0 + (staff_count * 10.0))
        leakage_risk = min(100.0, (cancelled / max(1, snapshot.get("orders", 1))) * 100.0)

        return calculate_health_score(
            revenue=revenue_component,
            inventory=inventory_component,
            waste=waste_component,
            orders=orders_component,
            customers=customers_component,
            operations=operations_component,
            leakage_risk=leakage_risk,
        )

    async def get_anomalies(self) -> List[Dict[str, Any]]:
        snapshot = await AIRepository.get_business_snapshot(self.conn) if self.conn is not None else {}
        if not snapshot.get("has_data"):
            return []
        series = snapshot.get("daily_revenue") or [0.0]
        return detect_anomalies(sales=series, orders=[max(1, len(series))] * len(series), discounts=[0.0] * len(series))

    async def get_revenue_leakage(self) -> Dict[str, Any]:
        snapshot = await AIRepository.get_business_snapshot(self.conn) if self.conn is not None else {}
        if not snapshot.get("has_data"):
            return {"status": "INSUFFICIENT_DATA", "message": "No recent revenue activity exists to evaluate leakage from the live database."}
        expected_revenue = float(snapshot.get("recent_revenue_30d") or snapshot.get("revenue") or 0.0)
        cancelled_orders = int(snapshot.get("cancelled_orders") or 0)
        leakage = max(0.0, cancelled_orders * 10.0)
        return {
            "risk_level": "LOW" if leakage < 25 else "MEDIUM" if leakage < 60 else "HIGH",
            "expected_revenue": round(expected_revenue, 2),
            "recorded_revenue": round(expected_revenue - leakage, 2),
            "difference": round(leakage, 2),
            "difference_percentage": round((leakage / max(1.0, expected_revenue)) * 100, 2),
            "possible_causes": ["Cancelled orders", "Refunds or adjustments", "Data reconciliation gaps"],
        }

    async def get_inventory_risks(self) -> List[Dict[str, Any]]:
        snapshot = await AIRepository.get_business_snapshot(self.conn) if self.conn is not None else {}
        if not snapshot.get("has_data"):
            return []
        inventory = []
        for item in (snapshot.get("popular_items") or [])[:3]:
            inventory.append({
                "item": item["name"],
                "current_stock": 0,
                "expected_demand": item["qty"],
                "stockout_risk": "MEDIUM" if item["qty"] >= 1 else "LOW",
                "estimated_stockout": datetime.utcnow().isoformat(),
                "recommended_purchase": max(0, int(item["qty"])),
            })
        return inventory

    async def get_waste_analysis(self) -> Dict[str, Any]:
        snapshot = await AIRepository.get_business_snapshot(self.conn) if self.conn is not None else {}
        if not snapshot.get("has_data"):
            return {"risks": [], "estimated_cost": 0}
        cancelled = int(snapshot.get("cancelled_orders") or 0)
        return {"risks": [{"item": "live_order_history", "cancelled_orders": cancelled, "waste_rate": 0.0, "estimated_monthly_cost": cancelled * 10.0}], "estimated_cost": cancelled * 10.0}

    async def get_sales_forecast(self) -> Dict[str, Any]:
        snapshot = await AIRepository.get_business_snapshot(self.conn) if self.conn is not None else {}
        if not snapshot.get("has_data"):
            return {"status": "INSUFFICIENT_DATA", "message": "Not enough recent revenue history is available for a valid sales forecast."}
        return sales_forecast(snapshot.get("daily_revenue") or [0.0])

    async def get_recommendations(self) -> List[Dict[str, Any]]:
        snapshot = await AIRepository.get_business_snapshot(self.conn) if self.conn is not None else {}
        if not snapshot.get("has_data"):
            return []
        items = snapshot.get("popular_items") or []
        if not items:
            return []
        return [
            build_recommendation(
                "SALES",
                "MEDIUM",
                f"Promote {item['name']}",
                "This menu item appears in the live order history and is a strong candidate for increased promotion.",
                "Highlight the item in recommendations and upsells.",
                0.75,
                [{"item": item["name"], "quantity": item["qty"]}],
                float(item["qty"]) * 10.0,
            )
            for item in items[:2]
        ]

    async def get_daily_summary(self) -> Dict[str, Any]:
        snapshot = await AIRepository.get_business_snapshot(self.conn) if self.conn is not None else {}
        if not snapshot.get("has_data"):
            return {"status": "INSUFFICIENT_DATA", "message": "The database does not yet contain enough recent operational data for a daily summary."}
        order_count = snapshot.get("recent_orders_30d") or snapshot.get("orders") or 0
        revenue = snapshot.get("recent_revenue_30d") or snapshot.get("revenue") or 0.0
        top_items = (snapshot.get("popular_items") or [])[:2]
        return {
            "headline": f"Recent live activity indicates {order_count} orders and ${revenue:,.2f} in revenue over the last 30 days.",
            "actions": [f"Prioritize {item['name']} in menu merchandising." for item in top_items] or ["Collect more order history to strengthen forecasting."],
        }

    async def inspect_quality(self, rows: Iterable[dict]) -> Dict[str, Any]:
        return assess_data_quality(rows)
