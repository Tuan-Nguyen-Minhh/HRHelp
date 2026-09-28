from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.db.base import Base


class ToolCall(Base):
    __tablename__ = "tool_calls"

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')",
            name="ck_tool_calls_status",
        ),
        Index("idx_tool_calls_agent_run_id", "agent_run_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    agent_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    tool_name = Column(String(255), nullable=False)
    input = Column(JSONB, nullable=True)
    output = Column(JSONB, nullable=True)
    status = Column(String(50), nullable=False, default="PENDING", server_default=text("'PENDING'"))
    started_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
