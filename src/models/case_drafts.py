from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base
from src.models.timestamp import TimestampMixin


class CaseDraft(TimestampMixin, Base):
    __tablename__ = "case_drafts"

    __table_args__ = (
        CheckConstraint(
            "draft_type IN ('MINUTES', 'EXPLANATION_REQUEST', 'DECISION', 'TICKET')",
            name="ck_case_drafts_draft_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'PENDING_REVIEW', 'APPROVED', 'REJECTED', 'ISSUED')",
            name="ck_case_drafts_status",
        ),
        Index("idx_case_drafts_case_id", "case_id"),
        Index("idx_case_drafts_recommendation_id", "recommendation_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    recommendation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("recommendations.id", ondelete="SET NULL"),
        nullable=True,
    )
    draft_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="DRAFT", server_default=text("'DRAFT'"))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
