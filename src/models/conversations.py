from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base
from src.models.timestamp import TimestampMixin


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'CLOSED')",
            name="ck_conversations_status",
        ),
        Index("idx_conversations_user_id", "user_id"),
        Index("idx_conversations_case_id", "case_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE", server_default=text("'ACTIVE'"))
