from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base


class AgentRetrieval(Base):
    """Chunks the retriever returned for one run. Citations live on the recommendation."""

    __tablename__ = "agent_retrievals"

    __table_args__ = (
        UniqueConstraint("agent_run_id", "rank", name="uq_agent_retrievals_run_rank"),
        UniqueConstraint("agent_run_id", "chunk_id", name="uq_agent_retrievals_run_chunk"),
        CheckConstraint("rank > 0", name="ck_agent_retrievals_rank"),
        Index("idx_agent_retrievals_chunk_id", "chunk_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    agent_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False)
    score = Column(Float, nullable=True)
    rank = Column(Integer, nullable=False)
    retrieval_method = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
