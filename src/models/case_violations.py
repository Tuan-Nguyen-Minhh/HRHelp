from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base


class CaseViolation(Base):
    __tablename__ = "case_violations"

    __table_args__ = (
        CheckConstraint(
            "severity IS NULL OR severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_case_violations_severity",
        ),
        Index("idx_case_violations_case_id", "case_id"),
        Index("idx_case_violations_violation_type_id", "violation_type_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    violation_type_id = Column(UUID(as_uuid=True), ForeignKey("violation_types.id"), nullable=False)
    evidence = Column(Text, nullable=True)
    severity = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
