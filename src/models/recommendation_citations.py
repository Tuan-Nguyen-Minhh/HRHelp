from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base


class RecommendationCitation(Base):
    """Legal basis the recommendation actually relied on."""

    __tablename__ = "recommendation_citations"

    __table_args__ = (
        Index("idx_recommendation_citations_recommendation_id", "recommendation_id"),
        Index("idx_recommendation_citations_chunk_id", "chunk_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    recommendation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recommendations.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    quote = Column(Text, nullable=False)
    article = Column(String(50), nullable=True)
    clause = Column(String(50), nullable=True)
    point = Column(String(50), nullable=True)
    score = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
