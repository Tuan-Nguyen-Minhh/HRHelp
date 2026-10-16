"""Allow the notification sent when a manager returns a case to HR.

Revision ID: 0013_manager_rejection_notice
Revises: 0012_conversation_working_state
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013_manager_rejection_notice"
down_revision: str | Sequence[str] | None = "0012_conversation_working_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PREVIOUS_EVENTS = (
    "'CASE_NEEDS_INFO', 'ASSESSMENT_READY', 'LEGAL_TICKET_SUBMITTED', "
    "'LEGAL_APPROVED', 'LEGAL_REJECTED', 'MANAGER_REVIEW_REQUESTED', "
    "'DECISION_ISSUED', 'CASE_CLOSED'"
)


def upgrade() -> None:
    op.drop_constraint("ck_notifications_event", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_event", "notifications", f"event IN ({_PREVIOUS_EVENTS}, 'MANAGER_REJECTED')"
    )


def downgrade() -> None:
    # Preserve the notice and its reason under the existing request-for-rework event.
    op.execute("UPDATE notifications SET event = 'CASE_NEEDS_INFO' WHERE event = 'MANAGER_REJECTED'")
    op.drop_constraint("ck_notifications_event", "notifications", type_="check")
    op.create_check_constraint("ck_notifications_event", "notifications", f"event IN ({_PREVIOUS_EVENTS})")
