from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.db.base import Base
from src.models.constants import SANCTION_TYPES_SQL
from src.models.timestamp import TimestampMixin


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'PENDING_REVIEW', 'APPROVED', 'REJECTED', 'SUPERSEDED')",
            name="ck_recommendations_status",
        ),
        CheckConstraint(
            f"sanction_type IS NULL OR sanction_type IN ({SANCTION_TYPES_SQL})",
            name="ck_recommendations_sanction_type",
        ),
        CheckConstraint(
            "risk_level IS NULL OR risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_recommendations_risk_level",
        ),
        Index("idx_recommendations_case_id", "case_id"),
        Index("idx_recommendations_agent_run_id", "agent_run_id"),
        Index("idx_recommendations_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    agent_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True)
    recommendation = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    sanction_type = Column(String(50), nullable=True)
    process_steps = Column(JSONB, nullable=True)
    risk_level = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False, default="DRAFT", server_default=text("'DRAFT'"))
