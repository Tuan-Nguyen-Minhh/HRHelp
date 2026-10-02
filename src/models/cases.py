from sqlalchemy import CheckConstraint, Column, Date, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base
from src.models.timestamp import TimestampMixin


class Case(TimestampMixin, Base):
    __tablename__ = "cases"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    case_code = Column(String(100), unique=True, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    employee_code = Column(String(100), nullable=True)
    employee_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    incident_date = Column(Date, nullable=True)
    status = Column(String(50), nullable=False, default="OPEN", server_default=text("'OPEN'"))
    family = Column(String(50), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'NEED_INFO', 'ANALYZED', 'PENDING_LEGAL', 'APPROVED', 'REJECTED', 'DECIDED', 'CLOSED')",
            name="ck_cases_status",
        ),
        Index("idx_cases_created_by", "created_by"),
        Index("idx_cases_status", "status"),
        Index("idx_cases_incident_date", "incident_date"),
        CheckConstraint(
            "family IS NULL OR family IN ('UNAUTHORIZED_ABSENCE', 'LATE', 'GENERAL')",
            name="ck_cases_family",
        ),
        Index("idx_cases_employee_code", "employee_code"),
    )
