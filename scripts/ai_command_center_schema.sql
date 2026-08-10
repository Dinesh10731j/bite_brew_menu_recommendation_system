-- AI Operations Command Center schema scaffolding
-- Safe, additive schema design that can be applied to a production PostgreSQL database.

CREATE TABLE IF NOT EXISTS ai_insights (
    id UUID PRIMARY KEY,
    type TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    evidence JSONB,
    recommendation TEXT,
    confidence NUMERIC(4,3) DEFAULT 0,
    status TEXT DEFAULT 'NEW',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ai_recommendations (
    id UUID PRIMARY KEY,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    impact JSONB,
    evidence JSONB,
    recommended_action TEXT,
    confidence NUMERIC(4,3) DEFAULT 0,
    status TEXT DEFAULT 'NEW',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ai_forecasts (
    id UUID PRIMARY KEY,
    type TEXT NOT NULL,
    period TEXT,
    forecast_value NUMERIC,
    lower_bound NUMERIC,
    upper_bound NUMERIC,
    confidence NUMERIC(4,3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_anomalies (
    id UUID PRIMARY KEY,
    type TEXT NOT NULL,
    metric TEXT,
    value NUMERIC,
    message TEXT,
    severity TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_model_runs (
    id UUID PRIMARY KEY,
    model_name TEXT,
    status TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ai_feedback (
    id UUID PRIMARY KEY,
    insight_id UUID,
    feedback_type TEXT,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_insights_status ON ai_insights(status);
CREATE INDEX IF NOT EXISTS idx_ai_insights_category ON ai_insights(category);
CREATE INDEX IF NOT EXISTS idx_ai_insights_created_at ON ai_insights(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_recommendations_status ON ai_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_ai_forecasts_type ON ai_forecasts(type);
CREATE INDEX IF NOT EXISTS idx_ai_anomalies_type ON ai_anomalies(type);
