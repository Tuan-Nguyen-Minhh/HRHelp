from sqlalchemy import Boolean, CheckConstraint, Column, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base
from src.models.timestamp import TimestampMixin


class ViolationType(TimestampMixin, Base):
    __tablename__ = "violation_types"

    __table_args__ = (
        CheckConstraint(
            "default_severity IS NULL OR default_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_violation_types_default_severity",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    code = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    default_severity = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
