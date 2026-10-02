from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base
from src.models.timestamp import TimestampMixin


class CaseFact(TimestampMixin, Base):
    __tablename__ = "case_facts"

    __table_args__ = (
        UniqueConstraint("case_id", "fact_key", name="uq_case_facts_case_key"),
        CheckConstraint(
            "(confirmed = FALSE AND confirmed_by IS NULL AND confirmed_at IS NULL) "
            "OR (confirmed = TRUE AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)",
            name="ck_case_facts_confirmed",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    fact_key = Column(String(100), nullable=False)
    fact_value = Column(Text, nullable=True)
    source_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    confirmed = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    confirmed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    confidence = Column(Float, nullable=True)
