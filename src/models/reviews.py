from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base


class Review(Base):
    __tablename__ = "reviews"

    __table_args__ = (
        CheckConstraint(
            "decision IN ('APPROVE', 'REJECT')",
            name="ck_reviews_decision",
        ),
        Index("idx_reviews_case_id", "case_id"),
        Index("idx_reviews_reviewer_id", "reviewer_id"),
        Index("idx_reviews_recommendation_id", "recommendation_id"),
        Index("idx_reviews_draft_id", "draft_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    recommendation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recommendations.id", ondelete="SET NULL"),
        nullable=True,
    )
    draft_id = Column(UUID(as_uuid=True), ForeignKey("case_drafts.id", ondelete="SET NULL"), nullable=True)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    decision = Column(String(50), nullable=False)
    comment = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
