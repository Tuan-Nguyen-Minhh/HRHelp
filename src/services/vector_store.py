from functools import lru_cache

from langchain_mistralai import MistralAIEmbeddings
from langchain_postgres import PGVector

from src.core.config import settings


@lru_cache
def get_vector_store() -> PGVector:
    """Vector store on the project Postgres database (pgvector).

    Embeddings: mistral-embed (1024-dim) theo DECISION 2026-09-26 trong
    src/core/config.py. Can MISTRAL_API_KEY trong .env.
    """
    embeddings = MistralAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.MISTRAL_API_KEY,
    )
    return PGVector(
        embeddings=embeddings,
        collection_name=settings.VECTOR_COLLECTION,
        connection=settings.VECTOR_DATABASE_URI,
        use_jsonb=True,
        create_extension=True,
    )
