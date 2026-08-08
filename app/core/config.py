from typing import List, Union
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
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
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

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


# Instantiated global settings singleton
settings = Settings()
