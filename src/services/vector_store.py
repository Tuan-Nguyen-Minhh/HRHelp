from functools import lru_cache

from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector

from src.core.config import settings


@lru_cache
def get_vector_store() -> PGVector:
    """Vector store on the project Postgres database (pgvector)."""
    embeddings = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    return PGVector(
        embeddings=embeddings,
        collection_name=settings.VECTOR_COLLECTION,
        connection=settings.VECTOR_DATABASE_URI,
        use_jsonb=True,
        create_extension=True,
    )
