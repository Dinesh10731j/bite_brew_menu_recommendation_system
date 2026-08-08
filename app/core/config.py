import json
from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings loaded from environment variables or .env file
    utilizing Pydantic V2 BaseSettings.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Configuration
    APP_NAME: str = "Bite & Brew AI Recommendation Service"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS Configuration
    # NOTE: The field type intentionally uses Union[List[str], str] rather than a
    # bare List[str]. Pydantic Settings V2 pre-runs json.loads() on complex-typed
    # (List) fields before the mode="before" validator runs, which would raise a
    # SettingsError for a plain comma-separated value like
    #   "http://localhost:3000,https://bitebrew.netlify.app"
    # (not valid JSON). The Union keeps the field from being treated as a
    # complex/JSON-only type, so comma-separated AND JSON-array environment
    # overrides both reach _parse_list_env() and are normalized to List[str].
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "https://bitebrew.netlify.app",
    ]
    CORS_ALLOW_CREDENTIALS: bool = False

    # Trusted Hosts (Host header allowlist)
    # Overridable via JSON array or comma-separated string, same as CORS_ORIGINS.
    ALLOWED_HOSTS: Union[List[str], str] = [
        "bitebrew.netlify.app",
        "bite-brew-menu-recommendation-system.onrender.com",
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
    ]

    # Database Configuration (Neon PostgreSQL)
    DATABASE_URL: str = Field(
        default="postgresql://neon_user:neon_password@ep-sample-pooler.us-east-1.aws.neon.tech/bite_brew_db?sslmode=require",
        description="PostgreSQL connection string with pgvector extension enabled",
    )
    DB_POOL_MIN_SIZE: int = 2
    DB_POOL_MAX_SIZE: int = 10
    DB_TIMEOUT_SECONDS: float = 10.0

    # Redis Configuration (Upstash / Local Redis)
    REDIS_URL: str = Field(
        default="",
        description="Redis connection URL (e.g. rediss://default:password@host:6379)",
    )
    CACHE_TTL_SECONDS: int = Field(
        default=3600,
        description="TTL duration in seconds for caching recommendation results in Redis",
    )
    ENABLE_CACHE: bool = Field(
        default=True,
        description="Flag to enable or disable Redis recommendation query caching",
    )

    # Machine Learning / Vector Embedding Configuration
    MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # Security Configuration
    API_KEY_SECRET: str = "dev-secret-key-12345"

    # HTTP Security Headers (Helmet) Configuration
    ENABLE_SECURITY_HEADERS: bool = Field(
        default=True,
        description="Enable Talisman HTTP security headers (Helmet for FastAPI).",
    )
    HSTS_MAX_AGE: int = Field(
        default=31536000,
        description="Strict-Transport-Security max-age in seconds (1 year default).",
    )
    HSTS_INCLUDE_SUBDOMAINS: bool = True
    HSTS_PRELOAD: bool = True
    CSP_ENABLED: bool = Field(
        default=True,
        description="Enable strict Content-Security-Policy header.",
    )
    CSP_DEFAULT_SRC: str = "'self'"
    CSP_CONNECT_SRC: str = "'self' https://bitebrew.netlify.app"

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="Globally enable or disable API rate limiting.",
    )
    DEFAULT_RATE_LIMIT: str = Field(
        default="100/minute",
        description="Global default rate limit applied to all requests.",
    )
    RECOMMEND_RATE_LIMIT: str = Field(
        default="60/minute",
        description="Per-IP rate limit for the expensive /recommend endpoint.",
    )
    PERSONALIZED_RECOMMEND_RATE_LIMIT: str = Field(
        default="60/minute",
        description="Per-IP rate limit for personalized recommendations.",
    )
    EVENT_RATE_LIMIT: str = Field(
        default="120/minute",
        description="Per-IP rate limit for capturing user behavior events.",
    )
    ORDER_RATE_LIMIT: str = Field(
        default="30/minute",
        description="Per-IP rate limit for recording user orders.",
    )
    HEALTH_RATE_LIMIT: str = Field(
        default="30/second",
        description="Rate limit for the health/readiness probe.",
    )

    @staticmethod
    def _parse_list_env(v: Union[str, List[str]]) -> List[str]:
        """
        Normalize an environment-provided list value into a Python List[str].

        Supports both accepted syntaxes for provider overrides:
          - JSON array string:  '["http://localhost:3000","https://bitebrew.netlify.app"]'
          - comma-separated:    'http://localhost:3000,https://bitebrew.netlify.app'
          - already a list passed programmatically.
        """
        if isinstance(v, str):
            candidate = v.strip()
            # Trim surrounding quotes if the whole value is wrapped in them.
            if (
                len(candidate) >= 2
                and candidate[0] == candidate[-1]
                and candidate[0] in ('"', "'")
            ):
                candidate = candidate[1:-1].strip()
            # JSON array form
            if candidate.startswith("[") and candidate.endswith("]"):
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except (json.JSONDecodeError, TypeError):
                    pass
            # Comma-separated form (fallback)
            return [item.strip() for item in candidate.split(",") if item.strip()]
        if isinstance(v, (list, tuple, set)):
            return [str(item).strip() for item in v if str(item).strip()]
        raise ValueError(f"Cannot parse list value from {v!r}")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        return cls._parse_list_env(v)

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v: Union[str, List[str]]) -> List[str]:
        return cls._parse_list_env(v)


# Instantiated global settings singleton
settings = Settings()
