from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
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
    # Text generation provider; embeddings always use Mistral.
    LLM_PROVIDER: Literal["deepseek", "mistral"] = "deepseek"
    MODEL_NAME: str = ""
    FALLBACK_MODEL_NAME: str = ""
    MISTRAL_BASE_URL: str = ""
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    LLM_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    SYSTEM_HELP_ENABLED: bool = True
    GENERAL_CHAT_ENABLED: bool = True
    GENERAL_CHAT_TIMEOUT_SECONDS: float = Field(default=20, ge=1, le=60)
    GENERAL_CHAT_RATE_LIMIT: int = Field(default=12, ge=1, le=120)
    INTENT_TOTAL_TIMEOUT_SECONDS: float = Field(default=60, ge=1, le=120)
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

    # Retrieval pools are deliberately separate from the evidence sent to chat.
    COHERE_API_KEY: str = ""
    COHERE_RERANK_MODEL: str = "rerank-v4.0-pro"
    COHERE_RERANK_TIMEOUT_SECONDS: float = Field(default=25, ge=1, le=120)
    RETRIEVAL_CANDIDATE_K: int = Field(default=40, ge=8, le=200)
    RETRIEVAL_FUSION_K: int = Field(default=100, ge=8, le=300)
    RETRIEVAL_FINAL_K: int = Field(default=12, ge=4, le=40)
    RETRIEVAL_BM25_MAX_CORPUS: int = Field(default=10000, ge=100, le=100000)
    # No universal relevance threshold: set only after domain calibration.
    RERANK_MIN_SCORE: float | None = Field(default=None, ge=0, le=1)
    RETRIEVAL_GRAPH_INCOMING: bool = False
    RETRIEVAL_EVIDENCE_MAX_BYTES: int = Field(default=40000, ge=1000, le=200000)
    # Optional exact tokenizer.json for the deployed chat model (never downloaded implicitly).
    SYNTHESIS_TOKENIZER_PATH: str = ""
    RETRIEVAL_EVIDENCE_TOKEN_BUDGET: int = Field(default=8000, ge=500, le=32000)
    SYNTHESIS_TIMEOUT_SECONDS: float = Field(default=300, ge=10, le=300)
    SYNTHESIS_TOTAL_TIMEOUT_SECONDS: float = Field(default=300, ge=10, le=600)
    SYNTHESIS_MAX_TOKENS: int = Field(default=12000, ge=1000, le=32000)
    SYNTHESIS_REASONING_EFFORT: Literal["none", "low", "high", "max"] = "low"

    @field_validator("RERANK_MIN_SCORE", mode="before")
    @classmethod
    def optional_rerank_threshold(cls, value):
        return None if value == "" else value

    # -------------------------
    # External research tools
    # -------------------------
    # Disabled by default. When enabled, the case graph may call an external
    # search/MCP bridge only for turns routed to external_research.
    EXTERNAL_RESEARCH_ENABLED: bool = False
    EXTERNAL_RESEARCH_PROVIDER: Literal["disabled", "brave", "tavily", "mcp_http"] = "disabled"
    EXTERNAL_RESEARCH_ALLOWED_DOMAINS: str = "chinhphu.vn,molisa.gov.vn,vbpl.vn"
    EXTERNAL_RESEARCH_MAX_RESULTS: int = Field(default=5, ge=1, le=10)
    EXTERNAL_RESEARCH_TIMEOUT_SECONDS: float = Field(default=12.0, ge=1.0, le=60.0)
    BRAVE_SEARCH_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    EXTERNAL_RESEARCH_MCP_URL: str = ""
    EXTERNAL_RESEARCH_MCP_TOOL_NAME: str = "web_search"

    # Uppercase on purpose: these property names mirror environment
    # variable names and are read from alembic/env.py, src/db/session.py,
    # src/services/vector_store.py and the scripts/ helpers. Renaming them
    # would break those call sites.
    @property
    def chat_api_key(self) -> str:
        """Credentials for the selected text provider, independent of embeddings."""
        key = self.DEEPSEEK_API_KEY if self.LLM_PROVIDER == "deepseek" else self.MISTRAL_API_KEY
        return key.strip()

    def chat_kwargs(self, model_name: str | None = None) -> dict[str, str]:
        """Model, credentials, and optional endpoint for the selected provider."""
        model = (model_name or self.MODEL_NAME).strip() or self.chat_models()[0]
        kwargs = {"model": model, "api_key": self.chat_api_key}
        if self.LLM_PROVIDER == "deepseek":
            kwargs["base_url"] = self.DEEPSEEK_BASE_URL.strip() or "https://api.deepseek.com"
        elif self.MISTRAL_BASE_URL.strip():
            kwargs["base_url"] = self.MISTRAL_BASE_URL.strip()
        return kwargs

    def chat_models(self) -> tuple[str, ...]:
        """Primary model first, then an optional fallback within the same provider."""
        default = "deepseek-flash" if self.LLM_PROVIDER == "deepseek" else "ministral-8b-2512"
        primary = self.MODEL_NAME.strip() or default
        fallback = self.FALLBACK_MODEL_NAME.strip()
        if fallback and fallback != primary:
            return (primary, fallback)
        return (primary,)

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
    # Admin document ingestion
    # -------------------------
    # Upper bound on an uploaded source file. The bytes are processed in memory
    # and never written to disk, so this guards request memory, not storage.
    MAX_UPLOAD_MB: int = 25

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
