from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base


class CaseAccess(Base):
    __tablename__ = "case_access"

    __table_args__ = (
        UniqueConstraint("case_id", "user_id", name="uq_case_access_case_user"),
        CheckConstraint(
            "access_level IN ('VIEW', 'REVIEW')",
            name="ck_case_access_access_level",
        ),
        Index("idx_case_access_user_id", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    access_level = Column(String(50), nullable=False)
    granted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
