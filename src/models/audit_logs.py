"""Append-only record of who changed a case and what changed."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.db.base import Base

AUDIT_ACTIONS = (
    "CASE_CREATED",
    "CASE_UPDATED",
    "FACT_CREATED",
    "FACT_CONFIRMED",
    "FACT_CHANGED",
    "RETRIEVAL_EXECUTED",
    "RECOMMENDATION_CREATED",
    "RECOMMENDATION_SUPERSEDED",
    "DISPATCH_PREVIEW_CREATED",
    "LEGAL_TICKET_SUBMITTED",
    "HR_ESCALATED",
    "LEGAL_APPROVED",
    "LEGAL_REJECTED",
    "CASE_REOPENED",
    "DECISION_ISSUED",
    "PRECEDENT_CREATED",
    "CASE_CLOSED",
    "ACCESS_GRANTED",
    "ACCESS_REVOKED",
    "DOCUMENT_INGESTED",
    "DOCUMENT_RETRIED",
)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("idx_audit_logs_case_id_created_at", "case_id", "created_at"),
        Index("idx_audit_logs_actor_id", "actor_id"),
        Index("idx_audit_logs_action", "action"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_role = Column(String(50), nullable=True)
    action = Column(String(64), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    before = Column(JSONB, nullable=True)
    after = Column(JSONB, nullable=True)
    audit_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
