from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base
from src.models.timestamp import TimestampMixin


class Policy(TimestampMixin, Base):
    __tablename__ = "policies"

    __table_args__ = (
        CheckConstraint(
            "policy_type IS NULL OR policy_type IN ('LAW', 'DECREE', 'CIRCULAR', 'INTERNAL_RULE', 'PRECEDENT')",
            name="ck_policies_policy_type",
        ),
        Index("idx_policies_policy_type", "policy_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    code = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    policy_type = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    deleted_at = Column(DateTime, nullable=True)
