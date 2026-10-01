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
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    API_V1_STR: str = "/api/v1"

    # -------------------------
    # LLM
    # -------------------------
    OPENAI_API_KEY: str = ""
    MODEL_NAME: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    # Clarify planner. OpenAI-compatible SpaceXAI endpoint. An empty key keeps
    # the chat turn on the safe clarification decision and does not retrieve.
    XAI_API_KEY: str = ""
    XAI_MODEL: str = "grok-4.7"
    XAI_BASE_URL: str = "https://api.x.ai/v1"

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
    # -------------------------
    # Embeddings (DECISION 2026-09-26, P-029):
    # Model chot: "mistral-embed" (text embeddings, 1024-dim, input toi da 8k
    # tokens theo doc Mistral; quota team: 20M TPM / 1 RPS).
    # Loai bo: "codestral-embed" (chi cho code retrieval, quota 50K TPM,
    # khong fit van ban luat tieng Viet) va OpenAI text-embedding-3-small
    # (template cu). Chunking tuong ung: tokenizer Mistral (mistral-common,
    # offline) + nguong 1000 tokens (~300 tu, tuong duong BGE-M3@500).
    # -------------------------
    MISTRAL_API_KEY: str = ""
    EMBEDDING_MODEL: str = "mistral-embed"
    EMBEDDING_DIMENSIONS: int = 1024
    EMBEDDING_MAX_TOKENS: int = 1000

    # Uppercase on purpose: these property names mirror environment
    # variable names and are read from alembic/env.py, src/db/session.py,
    # src/services/vector_store.py and the scripts/ helpers. Renaming them
    # would break those call sites.
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:  # noqa: N802
        return (
            f"postgresql+asyncpg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def SYNC_DATABASE_URI(self) -> str:  # noqa: N802
        return (
            f"postgresql+psycopg2://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def VECTOR_DATABASE_URI(self) -> str:  # noqa: N802
        # langchain-postgres requires the psycopg 3 driver name.
        return (
            f"postgresql+psycopg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # -------------------------
    # JWT
    # -------------------------
    JWT_SECRET: str = "change-me-in-env-before-you-share"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # -------------------------
    # Rate limit
    # -------------------------
    # RATE_LIMIT_CAPACITY: int
    # REFILL_RATE: int


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
