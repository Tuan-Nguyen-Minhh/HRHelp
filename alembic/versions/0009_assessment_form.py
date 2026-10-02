"""Store versioned assessment forms.

Revision ID: 0009_assessment_form
Revises: 0008_user_manage
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_assessment_form"
down_revision: str | Sequence[str] | None = "0008_user_manage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assessment_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'DRAFT'"), nullable=False),
        sa.Column("current_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT', 'CONFIRMED', 'SUPERSEDED')", name="ck_assessment_reports_status"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_assessment_reports_case_id", "assessment_reports", ["case_id"], unique=True)
    op.create_table(
        "assessment_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("edited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT', 'CONFIRMED', 'SUPERSEDED')", name="ck_assessment_versions_status"),
        sa.CheckConstraint("source IN ('AI', 'HR')", name="ck_assessment_versions_source"),
        sa.ForeignKeyConstraint(["edited_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["report_id"], ["assessment_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_assessment_versions_report_version",
        "assessment_versions",
        ["report_id", "version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_assessment_versions_report_version", table_name="assessment_versions")
    op.drop_table("assessment_versions")
    op.drop_index("uq_assessment_reports_case_id", table_name="assessment_reports")
    op.drop_table("assessment_reports")
