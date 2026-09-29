"""Vector retriever. It runs only when the query carries an embedding.

``document_chunks.embedding`` is 1536-dimensional. A vector of another width
is skipped so this arm cannot fail the BM25 and lexical arms.
"""

from src.features.cite.model.passage import Passage
from src.features.cite.model.query import SearchQuery
from src.features.cite.model.store import fetch_by_similarity, to_passage

EMBEDDING_DIM = 1536


async def similarity_passages(session, query: SearchQuery, limit: int) -> list[Passage]:
    """Nearest in-force chunks, or an empty list when no usable vector was supplied."""
    if query.embedding is None or len(query.embedding) != EMBEDDING_DIM:
        return []
    hits = await fetch_by_similarity(session, query.incident_date, list(query.embedding), limit)
    return [to_passage(hit) for hit in hits]
