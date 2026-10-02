"""Allow the manager-queue notification event.

Revision ID: 0007_manager_notice
Revises: 0006_enterprise_workflow
Create Date: 2026-10-01

HR can send a ready case straight to the manager, and legal approval also
notifies managers. The check constraint must accept that event.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_manager_notice"
down_revision: str | Sequence[str] | None = "0006_enterprise_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EVENTS = (
    "'CASE_NEEDS_INFO', 'ASSESSMENT_READY', 'LEGAL_TICKET_SUBMITTED', "
    "'LEGAL_APPROVED', 'LEGAL_REJECTED', 'MANAGER_REVIEW_REQUESTED', "
    "'DECISION_ISSUED', 'CASE_CLOSED'"
)


def upgrade() -> None:
    op.drop_constraint("ck_notifications_event", "notifications", type_="check")
    op.create_check_constraint("ck_notifications_event", "notifications", f"event IN ({_EVENTS})")


def downgrade() -> None:
    previous = (
        "'CASE_NEEDS_INFO', 'ASSESSMENT_READY', 'LEGAL_TICKET_SUBMITTED', "
        "'LEGAL_APPROVED', 'LEGAL_REJECTED', 'DECISION_ISSUED', 'CASE_CLOSED'"
    )
    op.execute("DELETE FROM notifications WHERE event = 'MANAGER_REVIEW_REQUESTED'")
    op.drop_constraint("ck_notifications_event", "notifications", type_="check")
    op.create_check_constraint("ck_notifications_event", "notifications", f"event IN ({previous})")
