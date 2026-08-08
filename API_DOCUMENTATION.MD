# Bite & Brew AI Recommendation Service — API Documentation

Version: `0.1.0` · Base URL: `http://localhost:8000` · Interactive Docs: `/docs` (Swagger) · `/redoc` (ReDoc)

Production-grade AI Menu Recommendation microservice using **FastAPI**, **Neon PostgreSQL (pgvector)**, **Upstash Redis**, and the **all-MiniLM-L6-v2** SentenceTransformers embedding model (384-dimensional vectors).

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [Global Response Format](#global-response-format)
4. [Error Handling & Status Codes](#error-handling--status-codes)
5. [Rate Limiting](#rate-limiting)
6. **Endpoints**
   - [GET / → Root Metadata](#get---root-metadata)
   - [GET /api/v1/health → Health & Readiness](#get-apiv1health--health--readiness)
   - [POST /api/v1/recommend → AI Menu Recommendations](#post-apiv1recommend--ai-menu-recommendations)
   - [POST /api/v1/users/{user_id}/events → Capture Behavior Event](#post-apiv1usersuser_idevents--capture-behavior-event)
   - [POST /api/v1/users/{user_id}/orders → Record Order History](#post-apiv1usersuser_idorders--record-order-history)
   - [GET /api/v1/users/{user_id}/recommendations → Personalized Recommendations](#get-apiv1usersuser_idrecommendations--personalized-recommendations)
7. [Data Models](#data-models)
8. [Caching Behavior](#caching-behavior)
9. [Security](#security)

---

## Getting Started

### Run the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Base URL

All API routes are prefixed with `http://localhost:8000/api/v1`.

---

## Authentication

API key authentication is **optional** and controlled by the `API_KEY_SECRET` environment variable.

| Behavior | Condition |
|---|---|
| **Disabled** | `API_KEY_SECRET` is empty or equals the default `dev-secret-key-12345`. |
| **Enabled** | Any other `API_KEY_SECRET` value requires a matching `X-API-Key` header on every request. |

**Header format when enabled:**

```
X-API-Key: <your_api_key_secret>
```

**Failure response:** `401 Unauthorized` with `Invalid or missing X-API-Key security header.`

---

## Global Response Format

Most endpoints return a consistent envelope:

| Field | Type | Description |
|---|---|---|
| `status` | `string` | Always `"success"` on a successful response. |
| `cached` | `boolean` | `true` when the response was served from the Upstash Redis cache. |

---

## Error Handling & Status Codes

| Status Code | Meaning |
|---|---|
| `200 OK` | Request succeeded. |
| `201 Created` | Resource created (events & orders). |
| `401 Unauthorized` | Invalid or missing `X-API-Key` header (when auth is enabled). |
| `422 Unprocessable Entity` | Request validation failed (schema or business rule). |
| `429 Too Many Requests` | Rate limit exceeded. Includes a `Retry-After` header. |
| `500 Internal Server Error` | Unhandled server error. |

**Standard error body:**

```json
{
  "detail": "Human-readable error message"
}
```

---

## Rate Limiting

Per-IP rate limiting is enforced via `slowapi`. Limits are shared across workers when `REDIS_URL` is configured; otherwise they fall back to a per-process in-memory store.

| Endpoint | Default Limit | Config Variable |
|---|---|---|
| Global default | `100/minute` | `DEFAULT_RATE_LIMIT` |
| `POST /api/v1/recommend` | `60/minute` | `RECOMMEND_RATE_LIMIT` |
| `GET /users/{user_id}/recommendations` | `60/minute` | `PERSONALIZED_RECOMMEND_RATE_LIMIT` |
| `POST /users/{user_id}/events` | `120/minute` | `EVENT_RATE_LIMIT` |
| `POST /users/{user_id}/orders` | `30/minute` | `ORDER_RATE_LIMIT` |
| `GET /api/v1/health` | `30/second` | `HEALTH_RATE_LIMIT` |

> **Note:** Limits are derived from the client IP (`X-Forwarded-For` if present, otherwise the socket address).

---

## Endpoints

### `GET /` → Root Metadata

Returns basic application metadata and links to key endpoints. *Not included in the OpenAPI schema.*

**Response `200 OK`:**

```json
{
  "app_name": "Bite & Brew AI Recommendation Service",
  "version": "0.1.0",
  "status": "running",
  "docs": "/docs",
  "health": "/api/v1/health",
  "recommend_endpoint": "/api/v1/recommend"
}
```

---

### `GET /api/v1/health` → Health & Readiness

Returns the operational status of the service, including the Neon PostgreSQL connection, Upstash Redis connection, and the ML embedding model singleton. Ideal for container orchestrators and monitoring probes.

**Rate limit:** `30/second` (`HEALTH_RATE_LIMIT`)

**Response Model:** `HealthCheckResponse`

**Response `200 OK`:**

```json
{
  "status": "ok",
  "environment": "development",
  "database_connected": true,
  "redis_connected": true,
  "embedding_model_loaded": true,
  "timestamp": "2025-01-01T12:00:00.000000+00:00"
}
```

| Field | Type | Description |
|---|---|---|
| `status` | `string` | `"ok"` or `"degraded"` (based on any dependency being reachable). |
| `environment` | `string` | Current running environment from `APP_ENV`. |
| `database_connected` | `boolean` | Neon PostgreSQL connection pool status. |
| `redis_connected` | `boolean` | Upstash Redis connection pool status. |
| `embedding_model_loaded` | `boolean` | SentenceTransformers singleton status. |
| `timestamp` | `string` | ISO 8601 server timestamp (UTC). |

---

### `POST /api/v1/recommend` → AI Menu Recommendations

Converts a natural-language user craving into a 384-dimensional vector embedding, then executes a **pgvector similarity search** (`<->` L2 distance operator) combined with optional price and category pre-filters.

**Rate limit:** `60/minute` (`RECOMMEND_RATE_LIMIT`)

**Request Model:** `RecommendationRequest`

**Request Body:**

```json
{
  "user_craving": "I want spicy and cheesy momo for lunch",
  "max_price": 200.0,
  "category": "Chicken",
  "top_n": 3
}
```

| Field | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `user_craving` | `string` | ✅ | — | 2–500 chars | Natural language craving. Leading/trailing whitespace is stripped; must not be empty. |
| `max_price` | `number` | ❌ | `null` | `> 0` | Optional maximum price threshold. |
| `category` | `string` | ❌ | `null` | ≤ 100 chars | Case-insensitive, partial-match category filter (e.g. `Veg`, `Chicken`, `Tea`). |
| `top_n` | `integer` | ❌ | `3` | 1–50 | Number of top recommendations to return. |

**Response Model:** `RecommendationResponse`

**Response `200 OK`:**

```json
{
  "status": "success",
  "query_craving": "I want spicy and cheesy momo for lunch",
  "filters_applied": {
    "max_price": 200.0,
    "category": "Chicken"
  },
  "total_matches": 2,
  "recommendations": [
    {
      "id": "6937aa7d-b073-42dd-a449-7595c884c480",
      "name": "Spicy Chicken Momo",
      "description": "Steamed dumplings filled with spiced chicken, served with chili dip.",
      "price": 180.0,
      "image": null,
      "image_url": "https://images.unsplash.com/photo-1626777552726",
      "category": {
        "id": "3f2a1b2c-0000-0000-0000-000000000001",
        "name": "Chicken",
        "description": "Chicken dishes"
      },
      "categoryId": "3f2a1b2c-0000-0000-0000-000000000001",
      "available": true,
      "featured": false,
      "discount": 0.0,
      "popularity": 42,
      "is_vegetarian": false,
      "match_score": 0.8845,
      "distance": 0.1155
    }
  ],
  "cached": false
}
```

**Errors:**

| HTTP | Detail |
|---|---|
| `422` | Validation error (e.g. empty craving, invalid `top_n`). |
| `500` | Internal server error while processing recommendations. |

---

### `POST /api/v1/users/{user_id}/events` → Capture Behavior Event

Records a single user behavior event (e.g. `view`, `like`, `favorite`, `add_to_cart`, `click`) that trains the user's learned taste profile for future personalized recommendations.

**Rate limit:** `120/minute` (`EVENT_RATE_LIMIT`)

**Path Parameter:**

| Param | Type | Description |
|---|---|---|
| `user_id` | `string` | The user performing the interaction. |

**Request Model:** `UserEventRequest`

**Request Body:**

```json
{
  "menu_item_id": "6937aa7d-b073-42dd-a449-7595c884c480",
  "event_type": "like",
  "metadata": {
    "source_page": "menu",
    "session_id": "abc123"
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `menu_item_id` | `string` / `int` / `UUID` | ✅ | Identifier of the menu item the user interacted with. |
| `event_type` | `string` | ✅ | One of: `view`, `like`, `favorite`, `add_to_cart`, `click`, `order`. Case-insensitive, lowercased. |
| `metadata` | `object` | ❌ | Optional extra context (e.g. source page, quantity, timestamp). |

**Response Model:** `EventProcessedResponse`

**Response `201 Created`:**

```json
{
  "status": "success",
  "user_id": "user_123",
  "event_type": "like",
  "menu_item_id": "6937aa7d-b073-42dd-a449-7595c884c480",
  "timestamp": "2025-01-01T12:00:00.000000+00:00"
}
```

**Errors:**

| HTTP | Detail |
|---|---|
| `422` | Invalid `event_type` or missing `menu_item_id`. |
| `500` | Failed to capture user event. |

---

### `POST /api/v1/users/{user_id}/orders` → Record Order History

Records a user's order (with its items). Ordered items become strong preference signals in the AI recommendation engine.

**Rate limit:** `30/minute` (`ORDER_RATE_LIMIT`)

**Path Parameter:**

| Param | Type | Description |
|---|---|---|
| `user_id` | `string` | The user placing the order. |

**Request Model:** `UserOrderRequest`

**Request Body:**

```json
{
  "items": [
    {
      "menu_item_id": "6937aa7d-b073-42dd-a449-7595c884c480",
      "quantity": 2,
      "price": 180.0
    },
    {
      "menu_item_id": 5,
      "quantity": 1
    }
  ],
  "total": 360.0,
  "status": "completed"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `items` | `array` | ✅ | At least 1 item. Each item: `menu_item_id` (required), `quantity` (int ≥ 1, default `1`), `price` (float ≥ 0, optional). |
| `total` | `number` | ❌ | Order total (≥ 0). |
| `status` | `string` | ❌ | Order status, default `"completed"`. |

**Response Model:** `OrderProcessedResponse`

**Response `201 Created`:**

```json
{
  "status": "success",
  "user_id": "user_123",
  "order_id": 42,
  "total": 360.0,
  "timestamp": "2025-01-01T12:00:00.000000+00:00"
}
```

**Errors:**

| HTTP | Detail |
|---|---|
| `422` | Empty `items` array or invalid item. |
| `500` | Failed to record user order. |

---

### `GET /api/v1/users/{user_id}/recommendations` → Personalized Recommendations

Returns dish recommendations personalized to a user based on their captured behavior events and order history, optionally blended with a live craving query. Items already ordered are excluded.

**Rate limit:** `60/minute` (`PERSONALIZED_RECOMMEND_RATE_LIMIT`)

**Path Parameter:**

| Param | Type | Description |
|---|---|---|
| `user_id` | `string` | The user to generate recommendations for. |

**Query Parameters:**

| Param | Type | Required | Default | Constraints | Description |
|---|---|---|---|---|---|
| `user_craving` | `string` | ❌ | `null` | 2–500 chars | Optional craving text to blend with the taste profile (30% craving / 70% profile). |
| `max_price` | `number` | ❌ | `null` | `> 0` | Max price filter. |
| `category` | `string` | ❌ | `null` | ≤ 100 chars | Category name filter (case-insensitive). |
| `top_n` | `integer` | ❌ | `5` | 1–50 | Number of personalized recommendations to return. |

**Response Model:** `PersonalizedRecommendationResponse`

**Example Request:**

```bash
curl "http://localhost:8000/api/v1/users/user_123/recommendations?user_craving=I%20love%20spicy%20momo&max_price=250&top_n=5"
```

**Response `200 OK`:**

```json
{
  "user_id": "user_123",
  "status": "success",
  "query_craving": "I love spicy momo",
  "filters_applied": {
    "max_price": 250.0,
    "category": null
  },
  "preference_summary": {
    "favorite_categories": ["Chicken", "Momo"],
    "total_orders": 3,
    "total_events": 12,
    "has_preference_profile": true
  },
  "total_matches": 5,
  "recommendations": [
    {
      "id": "6937aa7d-b073-42dd-a449-7595c884c480",
      "name": "Spicy Chicken Momo",
      "description": "Steamed dumplings filled with spiced chicken.",
      "price": 180.0,
      "category": "Chicken",
      "match_score": 0.9123,
      "distance": 0.0877
    }
  ],
  "cached": false
}
```

| Field | Type | Description |
|---|---|---|
| `preference_summary.favorite_categories` | `array<string>` | Top categories the user prefers. |
| `preference_summary.total_orders` | `integer` | Total orders placed. |
| `preference_summary.total_events` | `integer` | Total behavior events tracked. |
| `preference_summary.has_preference_profile` | `boolean` | Whether a learned taste profile exists. |

**Errors:**

| HTTP | Detail |
|---|---|
| `422` | Validation error in query parameters. |
| `500` | Internal server error generating personalized recommendations. |

> **Note:** If the user has no behavioral signals yet, the endpoint returns an empty `recommendations` array with `has_preference_profile: false` until events/orders are captured.

---

## Data Models

### DishRecommendation

Represents a single menu item returned in recommendation results.

| Field | Type | Description |
|---|---|---|
| `id` | `string` / `int` / `UUID` | Unique dish identifier. |
| `name` | `string` | Name of the menu item. |
| `description` | `string` | Culinary description of the dish. |
| `price` | `float` | Price of the dish. |
| `image` | `string·null` | Image URL (optional). |
| `image_url` | `string·null` | Alias image URL for backward compatibility. |
| `category` | `string` / `CategoryDetails` / `null` | Category name or object. |
| `categoryId` | `string·null` | Associated category UUID. |
| `available` | `boolean` | Availability flag. |
| `featured` | `boolean` | Featured dish flag. |
| `discount` | `float` | Discount amount. |
| `popularity` | `integer` | Popularity index score. |
| `is_vegetarian` | `boolean` | Dietary flag. |
| `match_score` | `float` | Similarity score between `0.0` and `1.0` (higher is better). |
| `distance` | `float` | Raw pgvector Euclidean L2 distance (`<->`) score. |

### CategoryDetails

| Field | Type | Description |
|---|---|---|
| `id` | `string` / `UUID` / `null` | Category identifier. |
| `name` | `string·null` | Category name. |
| `description` | `string·null` | Category description. |

### RecommendationFiltersApplied

Echo of the pre-filters applied to a recommendation query.

| Field | Type | Description |
|---|---|---|
| `max_price` | `float·null` | Maximum price filter applied. |
| `category` | `string·null` | Category filter applied. |

### UserPreferenceSummary

Summary of a user's learned taste profile.

| Field | Type | Description |
|---|---|---|
| `favorite_categories` | `array<string>` | Top preferred categories. |
| `total_orders` | `integer` | Total orders placed. |
| `total_events` | `integer` | Total behavior events tracked. |
| `has_preference_profile` | `boolean` | Whether a learned profile exists. |

---

## Caching Behavior

All recommendation-generation endpoints leverage an **Upstash Redis** (or local Redis) cache keyed by a SHA256 hash of the query parameters.

- `POST /api/v1/recommend` → cache key prefix `rec_cache_v2:`
- `GET /users/{user_id}/recommendations` → cache key prefix `personalized_v1:`

| Behavior | Detail |
|---|---|
| **Cache hit** | Response returned immediately with `cached: true`. |
| **Cache miss** | Computes the result, stores it, and returns with `cached: false`. |
| **TTL** | Controlled by `CACHE_TTL_SECONDS` (default `3600` seconds / 1 hour). |
| **Disable** | Set `ENABLE_CACHE=false` to disable caching. |

---

## Security

The service ships with production-grade security:

- **HTTP Security Headers** (Helmet-style middleware): HSTS, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, Content-Security-Policy, Referrer-Policy, and Permissions-Policy. Toggle via `ENABLE_SECURITY_HEADERS`.
- **CORS** — configurable via `CORS_ORIGINS` (defaults include `https://bitebrew.netlify.app` and localhost origins for MERN stack development).
- **TrustedHost Middleware** — whitelists allowed `Host` headers (`ALLOWED_HOSTS`) to prevent DNS rebinding.
- **Optional API Key Auth** — via `X-API-Key` header when `API_KEY_SECRET` is set.
- **Rate Limiting** — per-IP protection across all endpoints (see [Rate Limiting](#rate-limiting)).

---

*Generated from the FastAPI application source. Interactive docs auto-generated at `/openapi.json`, `/docs`, and `/redoc`.*
