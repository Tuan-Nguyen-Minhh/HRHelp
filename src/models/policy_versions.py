from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint

from src.db.base import Base


class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    __table_args__ = (
        UniqueConstraint("policy_id", "version", name="uq_policy_version"),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')",
            name="ck_policy_versions_status",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_policy_versions_effective_range",
        ),
        Index(
            "uq_policy_versions_one_active",
            "policy_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("idx_policy_versions_status", "status"),
        Index("idx_policy_versions_effective_from", "effective_from"),
        # effective_to is inclusive. uuid equality on gist needs gist_uuid_ops from btree_gist.
        ExcludeConstraint(
            ("policy_id", "="),
            (
                text(
                    "daterange(effective_from, "
                    "CASE WHEN effective_to IS NULL THEN NULL ELSE effective_to + 1 END, "
                    "'[)')"
                ),
                "&&",
            ),
            name="ex_policy_versions_no_overlap",
            using="gist",
            ops={"policy_id": "gist_uuid_ops"},
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    policy_id = Column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=False)
    version = Column(String(50), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE", server_default=text("'ACTIVE'"))
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
