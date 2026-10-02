"""In-app notices. The demo does not publish them to a broker."""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base

NOTIFICATION_EVENTS = (
    "CASE_NEEDS_INFO",
    "ASSESSMENT_READY",
    "LEGAL_TICKET_SUBMITTED",
    "LEGAL_APPROVED",
    "LEGAL_REJECTED",
    "MANAGER_REVIEW_REQUESTED",
    "DECISION_ISSUED",
    "CASE_CLOSED",
)


class Notification(Base):
    __tablename__ = "notifications"

    __table_args__ = (
        CheckConstraint(
            "event IN (" + ", ".join(f"'{item}'" for item in NOTIFICATION_EVENTS) + ")",
            name="ck_notifications_event",
        ),
        Index("idx_notifications_user_id_created_at", "user_id", "created_at"),
        Index("idx_notifications_case_id", "case_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    event = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
