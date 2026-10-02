"""Let a manager permission name be stored.

Revision ID: 0008_user_manage
Revises: 0007_manager_notice
Create Date: 2026-10-02

The permissions check constraint must accept user:manage before seed inserts it.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_user_manage"
down_revision: str | Sequence[str] | None = "0007_manager_notice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    "'case:open', 'case:read', 'case:chat', 'case:confirm', 'answer:read', "
    "'case:update', 'case:access', 'legal:review', 'decision:issue', 'decision:read', "
    "'case:close', 'case:reopen', 'dashboard:read', 'audit:read', 'document:manage', "
    "'notification:read', 'precedent:write', 'user:manage'"
)
_PREVIOUS = (
    "'case:open', 'case:read', 'case:chat', 'case:confirm', 'answer:read', "
    "'case:update', 'case:access', 'legal:review', 'decision:issue', 'decision:read', "
    "'case:close', 'case:reopen', 'dashboard:read', 'audit:read', 'document:manage', "
    "'notification:read', 'precedent:write'"
)


def upgrade() -> None:
    op.drop_constraint("ck_permissions_name", "permissions", type_="check")
    op.create_check_constraint("ck_permissions_name", "permissions", f"name IN ({_PERMISSIONS})")


def downgrade() -> None:
    op.execute(
        "DELETE FROM permission_roles WHERE permission_id IN (SELECT id FROM permissions WHERE name = 'user:manage')"
    )
    op.execute("DELETE FROM permissions WHERE name = 'user:manage'")
    op.drop_constraint("ck_permissions_name", "permissions", type_="check")
    op.create_check_constraint("ck_permissions_name", "permissions", f"name IN ({_PREVIOUS})")
