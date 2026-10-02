"""Versioned assessment document. A new edit adds a version and leaves the old one."""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.db.base import Base
from src.models.timestamp import TimestampMixin


class AssessmentReport(TimestampMixin, Base):
    __tablename__ = "assessment_reports"

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'CONFIRMED', 'SUPERSEDED')",
            name="ck_assessment_reports_status",
        ),
        Index("uq_assessment_reports_case_id", "case_id", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    recommendation_id = Column(UUID(as_uuid=True), ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), nullable=False, default="DRAFT", server_default=text("'DRAFT'"))
    current_version = Column(Integer, nullable=False, default=1, server_default=text("1"))


class AssessmentVersion(Base):
    __tablename__ = "assessment_versions"

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'CONFIRMED', 'SUPERSEDED')",
            name="ck_assessment_versions_status",
        ),
        CheckConstraint("source IN ('AI', 'HR')", name="ck_assessment_versions_source"),
        Index("uq_assessment_versions_report_version", "report_id", "version", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    report_id = Column(UUID(as_uuid=True), ForeignKey("assessment_reports.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)
    source = Column(String(20), nullable=False)
    payload = Column(JSONB, nullable=False)
    edited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
