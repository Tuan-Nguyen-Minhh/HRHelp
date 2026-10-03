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
    # Clarify and sanction synthesis. An empty key keeps chat on the rule
    # extractor and leaves the sanction level unset.
    OPENAI_API_KEY: str = ""
    MODEL_NAME: str = "gpt-4o-mini"
    # Empty uses api.openai.com. An OpenRouter key (sk-or-) uses that host when this stays empty.
    OPENAI_BASE_URL: str = ""
    LLM_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    # -------------------------
    # Chat fallback chain (planner + synthesis share it via src/services/chat.py):
    # valid OpenAI key -> MISTRAL_CHAT_MODEL -> MISTRAL_CHAT_FALLBACK_MODEL.
    # Placeholder keys are skipped, so a local .env with only MISTRAL_API_KEY
    # runs purely on Mistral free tier. ministral-8b-2512 (625k TPM / 3.13 RPS)
    # is the primary; ministral-3b-2512 (1.3M TPM / 12.5 RPS) is the fallback.
    # -------------------------
    MISTRAL_CHAT_MODEL: str = "ministral-8b-2512"
    MISTRAL_CHAT_FALLBACK_MODEL: str = "ministral-3b-2512"
    MISTRAL_BASE_URL: str = "https://api.mistral.ai/v1"
    # Unused by the case agents. Left so an old env file still loads.
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
    def openai_chat_kwargs(self) -> dict[str, str]:
        """Model and host for ChatOpenAI. An OpenRouter key is not sent to api.openai.com."""
        model = self.MODEL_NAME.strip() or "gpt-4o-mini"
        base = self.OPENAI_BASE_URL.strip()
        if not base and self.OPENAI_API_KEY.startswith("sk-or-"):
            base = "https://openrouter.ai/api/v1"
        if "openrouter.ai" in base and "/" not in model:
            model = f"openai/{model}"
        kwargs = {"model": model, "api_key": self.OPENAI_API_KEY}
        if base:
            kwargs["base_url"] = base
        return kwargs

    def openai_key_valid(self) -> bool:
        """A placeholder or empty key is not a candidate."""
        key = self.OPENAI_API_KEY.strip()
        return key.startswith("sk-") and "your-key" not in key and len(key) >= 20

    def mistral_key_valid(self) -> bool:
        """An empty or placeholder key leaves chat on the rule fallback."""
        key = self.MISTRAL_API_KEY.strip()
        return bool(key) and "your-mistral" not in key and len(key) >= 20

    def chat_candidates(self) -> list[dict[str, str]]:
        """Ordered LLM candidates. Skipped keys never produce a candidate."""
        out: list[dict[str, str]] = []
        if self.openai_key_valid():
            out.append({"label": "openai", **self.openai_chat_kwargs()})
        if self.mistral_key_valid():
            base = self.MISTRAL_BASE_URL.strip() or "https://api.mistral.ai/v1"
            primary = self.MISTRAL_CHAT_MODEL.strip() or "ministral-8b-2512"
            out.append(
                {
                    "label": f"mistral:{primary}",
                    "model": primary,
                    "api_key": self.MISTRAL_API_KEY,
                    "base_url": base,
                }
            )
            fallback = self.MISTRAL_CHAT_FALLBACK_MODEL.strip()
            if fallback and fallback != primary:
                out.append(
                    {
                        "label": f"mistral:{fallback}",
                        "model": fallback,
                        "api_key": self.MISTRAL_API_KEY,
                        "base_url": base,
                    }
                )
        return out

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:  # noqa: N802
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def SYNC_DATABASE_URI(self) -> str:  # noqa: N802
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def VECTOR_DATABASE_URI(self) -> str:  # noqa: N802
        # langchain-postgres requires the psycopg 3 driver name.
        return f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

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
