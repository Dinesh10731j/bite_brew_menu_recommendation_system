# AI Operations Command Center

## Overview

The AI Operations Command Center is an analytics layer layered on top of the existing Bite & Brew FastAPI application. It is designed to turn operational reporting from a historical snapshot into an explainable decision-support system.

The system answers five questions:

1. What happened?
2. Why did it happen?
3. What is likely to happen next?
4. What can cause financial loss?
5. What should management do next?

It intentionally avoids fabricating predictions. When data is missing or insufficient, the API returns `INSUFFICIENT_DATA` instead of guessing.

---

## Architecture

```text
Database / PostgreSQL
   ↓
AIRepository (table detection + safe aggregation)
   ↓
AICommandCenterService (statistics + explainable rules)
   ↓
FastAPI /api/ai routes
   ↓
Redis cache (optional) + business dashboard
```

This project already uses an async PostgreSQL pool and Redis. The command center reuses the same database manager and redis-friendly patterns without introducing a new service boundary.

---

## API Endpoints

### Base routes

- `GET /api/ai/command-center`
- `GET /api/ai/health-score`
- `GET /api/ai/anomalies`
- `GET /api/ai/revenue-leakage`
- `GET /api/ai/inventory-risks`
- `GET /api/ai/waste-analysis`
- `GET /api/ai/sales-forecast`
- `GET /api/ai/demand-forecast`
- `GET /api/ai/menu-insights`
- `GET /api/ai/staff-forecast`
- `GET /api/ai/customer-insights`
- `GET /api/ai/recommendations`
- `GET /api/ai/daily-summary`
- `POST /api/ai/recommendations/{id}/acknowledge`
- `POST /api/ai/recommendations/{id}/resolve`
- `POST /api/ai/recommendations/{id}/dismiss`

### Example request

```http
GET /api/ai/command-center
Accept: application/json
```

### Example response

```json
{
  "status": "OK",
  "period": {
    "start": "2026-08-03T00:00:00Z",
    "end": "2026-08-10T00:00:00Z"
  },
  "health_score": {
    "score": 82,
    "status": "HEALTHY",
    "components": {
      "revenue": 88,
      "inventory": 74,
      "waste": 81,
      "orders": 90,
      "customers": 79,
      "operations": 84
    }
  },
  "recommendations": [
    {
      "id": "...",
      "category": "INVENTORY",
      "severity": "HIGH",
      "title": "Chicken stockout risk",
      "description": "Current stock is below forecasted demand.",
      "impact": {
        "estimated_loss": 1850
      },
      "evidence": [
        {
          "current_stock": 8,
          "forecast_demand": 14
        }
      ],
      "recommended_action": "Purchase additional chicken.",
      "confidence": 0.91,
      "created_at": "2026-08-10T11:00:00Z"
    }
  ]
}
```

### Error response

```json
{
  "status": "INSUFFICIENT_DATA",
  "message": "No live operational data was found for the command center. Load orders, inventory, or sales history before running AI analytics.",
  "health_score": {
    "score": 0,
    "status": "INSUFFICIENT_DATA",
    "components": {}
  }
}
```

---

## Health Score Algorithm

The score is based on measurable operational components, all normalized to 0–100:

- Revenue health
- Inventory health
- Waste health
- Order health
- Customer health
- Operational health
- Revenue leakage risk (inverted)

Formula:

```text
health_score = revenue*0.24 + inventory*0.18 + waste*0.15 + orders*0.18 + customers*0.15 + operations*0.10 + (100 - leakage_risk)*0.10
```

Classification:

- 80–100: HEALTHY
- 60–79: WATCH
- below 60: RISK

---

## Anomaly Detection

The rule engine uses statistical thresholds with a simple z-score based detector. It flags unusual sales or order spikes and discount anomalies without labeling any employee as fraudulent.

Language is intentionally cautious:

- "Unusual sales detected. Review recommended."
- "Unusual activity detected. Review recommended."

---

## Revenue Leakage Detection

Revenue leakage compares:

- expected revenue
- recorded revenue
- discounts
- refunds
- cancellations
- voids

Formula:

```text
difference = expected_revenue - recorded_revenue
difference_percentage = (difference / expected_revenue) * 100
```

Risk thresholds:

- >= 10%: HIGH
- >= 5%: MEDIUM
- else: LOW

---

## Forecasting

Sales forecasting uses a weighted moving average based on the most recent sales history. The engine returns:

- forecast amount
- lower bound
- upper bound
- confidence score

The forecast is intentionally conservative and only produced when enough historical values exist. Otherwise it returns `INSUFFICIENT_DATA`.

---

## Confidence System

Confidence is kept between 0 and 1.

- 0.90–1.00: VERY_HIGH
- 0.75–0.89: HIGH
- 0.50–0.74: MODERATE
- below 0.50: LOW

If the dataset is too small or noisy, the response is `INSUFFICIENT_DATA` instead of presenting a false prediction.

---

## Data Quality Rules

Before analytics are generated, the engine validates:

- missing values
- negative quantities
- invalid prices
- duplicate records
- missing timestamps

The result includes a data-quality score and warnings, which prevents misleading recommendations from dirty data.

---

## Caching Strategy

This project already uses Redis. The command-center layer keeps expensive calculation results cache-friendly and uses short TTLs for fresh operational dashboards.

Suggested TTLs:

- command center: 1–5 minutes
- forecast: 30–60 minutes
- historical aggregates: longer TTL

---

## Background Jobs

Expensive analytics should be run in background tasks when available. The current implementation keeps the API responsive and falls back to safe in-memory calculations when live data is not yet available.

---

## Security and Tenant Isolation

All AI routes are protected by the same API-key validation flow already used by the current FastAPI project. The analytics layer assumes data is scoped to the relevant business or tenant and does not intentionally expose data across businesses.

---

## Failure Handling

The system is designed not to block the rest of the bakery or cafe application:

- missing Redis → fallback to direct database processing
- missing business data → `INSUFFICIENT_DATA`
- analytics failure → return an error with a safe message
- forecasting failure → keep the reporting system operational

---

## Database Schema Notes

The application does not currently include a full SQLAlchemy migration system for AI tables, but the command-center pattern is compatible with the following table design:

```sql
CREATE TABLE IF NOT EXISTS ai_insights (
    id UUID PRIMARY KEY,
    type TEXT,
    category TEXT,
    severity TEXT,
    title TEXT,
    description TEXT,
    evidence JSONB,
    recommendation TEXT,
    confidence NUMERIC(4,3),
    status TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ai_recommendations (
    id UUID PRIMARY KEY,
    category TEXT,
    severity TEXT,
    title TEXT,
    description TEXT,
    impact JSONB,
    evidence JSONB,
    recommended_action TEXT,
    confidence NUMERIC(4,3),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'NEW'
);

CREATE TABLE IF NOT EXISTS ai_forecasts (
    id UUID PRIMARY KEY,
    type TEXT,
    period TEXT,
    forecast_value NUMERIC,
    lower_bound NUMERIC,
    upper_bound NUMERIC,
    confidence NUMERIC(4,3),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_anomalies (
    id UUID PRIMARY KEY,
    type TEXT,
    metric TEXT,
    value NUMERIC,
    message TEXT,
    severity TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Environment and Deployment Notes

The runtime expects the existing application environment variables, including:

- `DATABASE_URL`
- `REDIS_URL`
- `API_KEY_SECRET`
- `APP_ENV`

No autonomous purchasing, price changes, or staff actions are implemented in this version. The command center is a recommendation and alert system, not an automated control system.
