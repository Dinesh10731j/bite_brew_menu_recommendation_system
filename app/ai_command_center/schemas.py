from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PeriodSchema(BaseModel):
    start: str
    end: str


class HealthScoreSchema(BaseModel):
    score: float = Field(ge=0, le=100)
    status: str
    components: Dict[str, float]
    message: Optional[str] = None


class RevenueLeakageSchema(BaseModel):
    risk_level: str
    expected_revenue: float
    recorded_revenue: float
    difference: float
    difference_percentage: float
    possible_causes: List[str] = Field(default_factory=list)


class RecommendationSchema(BaseModel):
    id: str
    category: str
    severity: str
    title: str
    description: str
    impact: Dict[str, float]
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_action: str
    confidence: float
    created_at: datetime


class AICommandCenterResponse(BaseModel):
    status: str
    period: Dict[str, str]
    health_score: Dict[str, Any]
    financial: Dict[str, Any]
    sales: Dict[str, Any]
    inventory: Dict[str, Any]
    waste: Dict[str, Any]
    menu: Dict[str, Any]
    customers: Dict[str, Any]
    staff: Dict[str, Any]
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    daily_summary: Dict[str, Any]
    message: Optional[str] = None
