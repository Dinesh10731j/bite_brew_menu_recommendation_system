from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class BusinessMetrics:
    """Normalized metrics used by command-center analytics."""

    total_revenue: float = 0.0
    total_orders: int = 0
    avg_order_value: float = 0.0
    top_item: str = "N/A"
    revenue_trend: float = 0.0
    total_items: int = 0
    inventory_count: int = 0
    customer_count: int = 0
    staff_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Insight:
    """Persistent insight stored in the operational intelligence layer."""

    id: str
    type: str
    category: str
    severity: str
    title: str
    description: str
    recommendation: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    status: str = "NEW"
    created_at: datetime = field(default_factory=lambda: datetime.utcnow())
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
