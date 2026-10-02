"""Signer and admin roles, audit, notifications, and idempotency.

Revision ID: 0006_enterprise_workflow
Revises: 0005_rbac
Create Date: 2026-10-01

Adds the columns and tables the legal-review, decision, and operations
routes need. Existing case, recommendation, and corpus rows are left in place.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_enterprise_workflow"
down_revision: str | Sequence[str] | None = "0005_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLES = "'HR', 'MANAGER', 'LEGAL', 'SIGNER', 'ADMIN'"
_PERMISSIONS = (
    "'case:open', 'case:read', 'case:chat', 'case:confirm', 'answer:read', "
    "'case:update', 'case:access', 'legal:review', 'decision:issue', 'decision:read', "
    "'case:close', 'case:reopen', 'dashboard:read', 'audit:read', 'document:manage', "
    "'notification:read', 'precedent:write'"
)
_EVENTS = (
    "'CASE_NEEDS_INFO', 'ASSESSMENT_READY', 'LEGAL_TICKET_SUBMITTED', "
    "'LEGAL_APPROVED', 'LEGAL_REJECTED', 'DECISION_ISSUED', 'CASE_CLOSED'"
)


def upgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", f"role IN ({_ROLES})")
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    op.drop_constraint("ck_roles_name", "roles", type_="check")
    op.create_check_constraint("ck_roles_name", "roles", f"name IN ({_ROLES})")

    op.drop_constraint("ck_permissions_name", "permissions", type_="check")
    op.create_check_constraint("ck_permissions_name", "permissions", f"name IN ({_PERMISSIONS})")

    op.drop_constraint("ck_case_access_access_level", "case_access", type_="check")
    op.create_check_constraint(
        "ck_case_access_access_level",
        "case_access",
        "access_level IN ('VIEW', 'REVIEW', 'EDIT')",
    )

    op.add_column("cases", sa.Column("family", sa.String(length=50), nullable=True))
    op.create_check_constraint(
        "ck_cases_family",
        "cases",
        "family IS NULL OR family IN ('UNAUTHORIZED_ABSENCE', 'LATE', 'GENERAL')",
    )

    op.add_column("case_facts", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("policies", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index(
        "uq_documents_content_hash",
        "documents",
        ["content_hash"],
        unique=True,
        postgresql_where=sa.text("content_hash IS NOT NULL"),
    )

    op.add_column("agent_runs", sa.Column("agent_name", sa.String(length=100), nullable=True))
    op.add_column("agent_runs", sa.Column("graph_name", sa.String(length=100), nullable=True))
    op.add_column("agent_runs", sa.Column("total_tokens", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("agent_retrievals", sa.Column("retrieval_method", sa.String(length=50), nullable=True))
    op.add_column("tool_calls", sa.Column("duration_ms", sa.Integer(), nullable=True))

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_role", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_logs_case_id_created_at", "audit_logs", ["case_id", "created_at"])
    op.create_index("idx_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(f"event IN ({_EVENTS})", name="ck_notifications_event"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_notifications_user_id_created_at", "notifications", ["user_id", "created_at"])
    op.create_index("idx_notifications_case_id", "notifications", ["case_id"])

    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'IN_PROGRESS'"), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor_id", "route", "idempotency_key", name="uq_idempotency_actor_route_key"),
    )
    op.create_index("idx_idempotency_keys_created_at", "idempotency_keys", ["created_at"])

    op.create_table(
        "revoked_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )


def downgrade() -> None:
    op.drop_table("revoked_tokens")
    op.drop_index("idx_idempotency_keys_created_at", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.drop_index("idx_notifications_case_id", table_name="notifications")
    op.drop_index("idx_notifications_user_id_created_at", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("idx_audit_logs_action", table_name="audit_logs")
    op.drop_index("idx_audit_logs_actor_id", table_name="audit_logs")
    op.drop_index("idx_audit_logs_case_id_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_column("tool_calls", "duration_ms")
    op.drop_column("agent_retrievals", "retrieval_method")
    op.drop_column("agent_runs", "metadata")
    op.drop_column("agent_runs", "total_tokens")
    op.drop_column("agent_runs", "graph_name")
    op.drop_column("agent_runs", "agent_name")

    op.drop_index("uq_documents_content_hash", table_name="documents")
    op.drop_column("documents", "deleted_at")
    op.drop_column("policies", "deleted_at")
    op.drop_column("case_facts", "confidence")
    op.drop_constraint("ck_cases_family", "cases", type_="check")
    op.drop_column("cases", "family")

    op.drop_constraint("ck_case_access_access_level", "case_access", type_="check")
    op.create_check_constraint(
        "ck_case_access_access_level",
        "case_access",
        "access_level IN ('VIEW', 'REVIEW')",
    )
    op.drop_constraint("ck_permissions_name", "permissions", type_="check")
    op.create_check_constraint(
        "ck_permissions_name",
        "permissions",
        "name IN ('case:open', 'case:read', 'case:chat', 'case:confirm', 'answer:read')",
    )
    op.drop_constraint("ck_roles_name", "roles", type_="check")
    op.create_check_constraint("ck_roles_name", "roles", "name IN ('HR', 'MANAGER', 'LEGAL')")
    op.drop_column("users", "deleted_at")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint("ck_users_role", "users", "role IN ('HR', 'MANAGER', 'LEGAL')")
