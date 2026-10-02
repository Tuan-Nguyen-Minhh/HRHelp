from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.db.base import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')",
            name="ck_agent_runs_status",
        ),
        Index("idx_agent_runs_conversation_id", "conversation_id"),
        Index("idx_agent_runs_message_id", "message_id"),
        Index("idx_agent_runs_output_message_id", "output_message_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    output_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), nullable=False, default="PENDING", server_default=text("'PENDING'"))
    model = Column(String(100), nullable=True)
    model_version = Column(String(100), nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    agent_name = Column(String(100), nullable=True)
    graph_name = Column(String(100), nullable=True)
    total_tokens = Column(Integer, nullable=True)
    run_metadata = Column("metadata", JSONB, nullable=True)
