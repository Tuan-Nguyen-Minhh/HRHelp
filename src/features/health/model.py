"""Check the database, pgvector, and whether model credentials are configured."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings


async def readiness(session: AsyncSession) -> tuple[bool, dict]:
    """Return whether required dependencies answer. Values are booleans, not secrets."""
    database = await _database(session)
    vector = await _vector(session) if database else False
    llm = bool(settings.chat_api_key)
    embedding = bool(settings.MISTRAL_API_KEY) and settings.EMBEDDING_MODEL == "mistral-embed"
    checks = {
        "database": database,
        "pgvector": vector,
        "llm_configured": llm,
        "embedding_configured": embedding,
    }
    return database and vector and llm and embedding, checks


async def _database(session: AsyncSession) -> bool:
    try:
        await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _vector(session: AsyncSession) -> bool:
    try:
        found = await session.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        return bool(found)
    except Exception:
        return False
