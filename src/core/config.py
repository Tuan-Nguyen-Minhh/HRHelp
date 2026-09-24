from functools import lru_cache
from pathlib import Path

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
    # PROJECT_NAME: str = "Auth_Jwt"
    API_V1_STR: str = "/api/v1"

    # -------------------------
    # Database
    # -------------------------
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str

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