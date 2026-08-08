# Bite & Brew — AI Menu Recommendation Microservice

A production-grade, asynchronous FastAPI microservice powering the **Bite & Brew** food recommendation platform. It interfaces directly with a Neon PostgreSQL database using the `pgvector` extension to deliver high-performance hybrid semantic vector search and menu filtering.

---

## 🌟 Key Features

- **FastAPI Core**: Async route architecture with strict Pydantic v2 validation.
- **Neon PostgreSQL + pgvector**: Vector distance operator `<->` queries for exact/approximate nearest neighbor dish search.
- **ML Singleton Model**: Pre-loads `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional vector output) during app lifespan startup to minimize request latency.
- **Connection Pooling**: Managed `psycopg3` async connection pool (`AsyncConnectionPool`) with resilience and automatic cleanup.
- **CORS Configured**: Ready for MERN stack (React / Express) and web integration.
- **Admin Utilities**:
  - `scripts/seed_menu.py`: Seed culinary menu items into Neon DB with initial embeddings.
  - `scripts/sync_embeddings.py`: Batch generate missing vector embeddings for newly added dishes.
- **Multi-Stage Docker**: Containerized build pre-downloading model weights to ensure zero startup download overhead.

---

## 🏗 Directory Architecture

```
bite-brew-ai-service/
├── .env.example              # Sample environment variables
├── .gitignore                # Git exclusions
├── Dockerfile                # Multi-stage production Docker image
├── README.md                 # Project documentation
├── pyproject.toml            # Project configuration & tool settings
├── requirements.txt          # Python dependencies
│
├── app/                      # Main Application Package
│   ├── main.py               # FastAPI entrypoint, lifespan events, CORS
│   ├── api/                  # API endpoints
│   │   ├── deps.py           # Dependency injection (DB pool, service access)
│   │   └── v1/
│   │       ├── health.py     # Liveness/readiness probes
│   │       └── recommend.py  # Recommendation endpoint (/api/v1/recommend)
│   ├── core/                 # App configuration & Infrastructure
│   │   ├── config.py         # Pydantic Settings
│   │   ├── database.py       # Neon PostgreSQL connection pool
│   │   └── logger.py         # JSON structured logger
│   ├── db/                   # Data Access Layer
│   │   └── repository.py     # pgvector queries with SQL pre-filtering
│   ├── models/               # ML Embeddings Singleton
│   │   └── embedder.py       # SentenceTransformer wrapper singleton
│   ├── schemas/              # Pydantic Request & Response DTOs
│   │   ├── request.py        # RecommendationRequest schema
│   │   └── response.py       # RecommendationResponse schema
│   └── services/             # Business Logic Layer
│       └── recommendation.py # Recommendation orchestration service
│
├── scripts/                  # Operational scripts
│   ├── seed_menu.py          # Create tables & insert initial menu items
│   └── sync_embeddings.py    # Batch encode dishes missing embeddings
│
└── tests/                    # Test Suite
    ├── conftest.py           # Test fixtures and test client setup
    ├── test_health.py        # Unit tests for /health endpoints
    └── test_recommend.py     # Unit tests for /recommend endpoint
```

---

## 🚀 Quick Start Guide

### 1. Requirements

- Python 3.10+
- Access to a Neon PostgreSQL Database (or local PostgreSQL with `pgvector` enabled)

### 2. Environment Setup

Copy `.env.example` to `.env` and configure your database credentials:

```bash
cp .env.example .env
```

Update your `DATABASE_URL` in `.env`:
```ini
DATABASE_URL="postgresql://neon_user:neon_password@ep-sample-pooler.us-east-1.aws.neon.tech/bite_brew_db?sslmode=require"
```

### 3. Installation

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 🛠 Database & Embedding Utilities

### Seed Database
Initialize table structure and insert sample menu items:
```bash
python -m scripts.seed_menu
```

### Batch Sync Embeddings
Generate vector embeddings for any database items missing embeddings:
```bash
python -m scripts.sync_embeddings
```

---

## 🏃 Running the Application

### Local Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The interactive OpenAPI documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 📡 API Endpoints Summary

### `POST /api/v1/recommend`
Generates personalized menu dish recommendations based on user craving context and filters.

**Request Payload:**
```json
{
  "user_craving": "I want something spicy and cheesy for lunch",
  "max_price": 18.50,
  "is_vegetarian": true,
  "top_n": 3
}
```

**Response Payload:**
```json
{
  "status": "success",
  "query_craving": "I want something spicy and cheesy for lunch",
  "filters_applied": {
    "max_price": 18.5,
    "is_vegetarian": true
  },
  "total_matches": 2,
  "recommendations": [
    {
      "id": 4,
      "name": "Spicy Paneer Tikka Wrap",
      "description": "Grilled marinated paneer wrapped with melted cheese, bell peppers, and chipotle mayo.",
      "category": "Wraps",
      "price": 14.99,
      "is_vegetarian": true,
      "image_url": "https://images.unsplash.com/photo-1626777552726-4a6b54c97e46",
      "match_score": 0.8845,
      "distance": 0.1155
    }
  ]
}
```

### `GET /api/v1/health`
Checks API server status and Neon PostgreSQL database connectivity.

---

## 🧪 Running Automated Tests

Run the test suite using `pytest`:

```bash
pytest -v
```

---

## 🐳 Docker Deployment

Build and run using Docker:

```bash
docker build -t bite-brew-ai-service .
docker run -p 8000:8000 --env-file .env bite-brew-ai-service
```

---

## 🔐 Production Security Features

The microservice ships with production-grade security out of the box:

### HTTP Security Headers (Helmet-style custom middleware)
Automatically injects hardened response headers, including:
- **Strict-Transport-Security** (HSTS) with configurable max-age, subdomains and preload.
- **X-Frame-Options: DENY** (frame/clickjacking protection).
- **X-Content-Type-Options: nosniff**.
- **Content-Security-Policy** (CSP) restricting loaded resources to the app origin.
- **Referrer-Policy** and **Permissions-Policy** limiting what the frontend can access.

Toggle via `ENABLE_SECURITY_HEADERS` and tune CSP via `CSP_ENABLED` / `CSP_DEFAULT_SRC` / `CSP_CONNECT_SRC`. When `DEBUG=false` (production), HTTPS redirects are enforced.

### Rate Limiting (`slowapi`)
Per-IP rate limiting to protect expensive AI endpoints from abuse:
- Global default limit via `DEFAULT_RATE_LIMIT`.
- Endpoint-specific limits:
  - `POST /api/v1/recommend` → `RECOMMEND_RATE_LIMIT` (e.g. `60/minute`)
  - `GET .../users/{id}/recommendations` → `PERSONALIZED_RECOMMEND_RATE_LIMIT`
  - `POST .../events` → `EVENT_RATE_LIMIT`
  - `POST .../orders` → `ORDER_RATE_LIMIT`
  - `GET /api/v1/health` → `HEALTH_RATE_LIMIT`

Exceeding a limit returns **429 Too Many Requests** with a `Retry-After` header.

> **Multi-worker note:** When `REDIS_URL` is set, limits are shared across all workers (recommended for production). Without Redis the limiter falls back to a per-process in-memory store.

### CORS + TrustedHost
- `CORS_ORIGINS` includes `https://bitebrew.netlify.app` for the production frontend, plus localhost origins for local development.
- `ALLOWED_HOSTS` whitelists trusted `Host` headers to prevent DNS rebinding attacks.

### Configuration
All security features are configurable through environment variables (see `.env.example`).
