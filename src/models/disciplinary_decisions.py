from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base
from src.models.constants import SANCTION_TYPES_SQL
from src.models.timestamp import TimestampMixin


class DisciplinaryDecision(TimestampMixin, Base):
    __tablename__ = "disciplinary_decisions"

    __table_args__ = (
        CheckConstraint(
            f"sanction_type IN ({SANCTION_TYPES_SQL})",
            name="ck_disciplinary_decisions_sanction_type",
        ),
        CheckConstraint(
            "NOT is_precedent OR precedent_summary IS NOT NULL",
            name="ck_disciplinary_decisions_precedent_summary",
        ),
        Index("idx_disciplinary_decisions_issued_by", "issued_by"),
        Index(
            "idx_disciplinary_decisions_precedent",
            "is_precedent",
            postgresql_where=text("is_precedent"),
        ),
        Index(
            "idx_disciplinary_decisions_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text("is_precedent AND embedding IS NOT NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True)
    draft_id = Column(UUID(as_uuid=True), ForeignKey("case_drafts.id", ondelete="SET NULL"), nullable=True)
    decision_code = Column(String(100), unique=True, nullable=False)
    sanction_type = Column(String(50), nullable=False)
    summary = Column(Text, nullable=False)
    legal_basis = Column(Text, nullable=True)
    storage_path = Column(String(1000), nullable=True)
    issued_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    issued_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    is_precedent = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    precedent_summary = Column(Text, nullable=True)
    embedding = Column(Vector(1536), nullable=True)
