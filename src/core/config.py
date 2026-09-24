from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -------------------------
    # App
    # -------------------------
    APP_NAME: str = "AI20K Agent"
    APP_ENV: Literal["development", "production", "test"] = "development"
    APP_PORT: int = Field(default=8000, ge=1, le=65535)
    APP_HOST: str = "0.0.0.0"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    CORS_ORIGINS: str = "http://localhost:3000"
    API_V1_STR: str = "/api/v1"

    # -------------------------
    # LLM
    # -------------------------
    OPENAI_API_KEY: str = ""
    MODEL_NAME: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)

    # -------------------------
    # Database
    # -------------------------
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str

    # pgvector lives in the same Postgres database.
    VECTOR_COLLECTION: str = "regulations"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def SYNC_DATABASE_URI(self) -> str:
        return (
            f"postgresql+psycopg2://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def VECTOR_DATABASE_URI(self) -> str:
        # langchain-postgres requires the psycopg 3 driver name.
        return (
            f"postgresql+psycopg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # -------------------------
    # JWT
    # -------------------------
    # JWT_SECRET: str
    # JWT_ALGORITHM: str = "HS256"
    #
    # ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # -------------------------
    # Rate limit
    # -------------------------
    # RATE_LIMIT_CAPACITY: int
    # REFILL_RATE: int


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
