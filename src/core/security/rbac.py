"""Role and permission names.

The enums are the source of truth. Startup copies them into ``roles``,
``permissions`` and ``permission_roles``. A request checks the lists embedded
in the access token, not this map.
"""

from enum import StrEnum


class RoleEnum(StrEnum):
    """Roles stored on ``users.role``."""

    HR = "HR"
    MANAGER = "MANAGER"
    LEGAL = "LEGAL"
    SIGNER = "SIGNER"
    ADMIN = "ADMIN"


class PermissionEnum(StrEnum):
    """Actions the case routes accept."""

    CASE_OPEN = "case:open"
    CASE_READ = "case:read"
    CASE_CHAT = "case:chat"
    CASE_CONFIRM = "case:confirm"
    ANSWER_READ = "answer:read"
    CASE_UPDATE = "case:update"
    CASE_ACCESS = "case:access"
    LEGAL_REVIEW = "legal:review"
    DECISION_ISSUE = "decision:issue"
    DECISION_READ = "decision:read"
    CASE_CLOSE = "case:close"
    CASE_REOPEN = "case:reopen"
    DASHBOARD_READ = "dashboard:read"
    AUDIT_READ = "audit:read"
    DOCUMENT_MANAGE = "document:manage"
    NOTIFICATION_READ = "notification:read"
    PRECEDENT_WRITE = "precedent:write"
    USER_MANAGE = "user:manage"


_HR = [
    PermissionEnum.CASE_OPEN.value,
    PermissionEnum.CASE_READ.value,
    PermissionEnum.CASE_CHAT.value,
    PermissionEnum.CASE_CONFIRM.value,
    PermissionEnum.ANSWER_READ.value,
    PermissionEnum.CASE_UPDATE.value,
    PermissionEnum.CASE_ACCESS.value,
    PermissionEnum.CASE_CLOSE.value,
    PermissionEnum.CASE_REOPEN.value,
    PermissionEnum.DASHBOARD_READ.value,
    PermissionEnum.NOTIFICATION_READ.value,
]

# Seed data only. Runtime authorization reads the token.
DEFAULT_ROLE_PERMISSIONS: dict[RoleEnum, list[str]] = {
    RoleEnum.HR: list(_HR),
    RoleEnum.MANAGER: [
        *list(_HR),
        PermissionEnum.DECISION_READ.value,
        PermissionEnum.DECISION_ISSUE.value,
        PermissionEnum.USER_MANAGE.value,
    ],
    RoleEnum.LEGAL: [
        PermissionEnum.LEGAL_REVIEW.value,
        PermissionEnum.ANSWER_READ.value,
        PermissionEnum.NOTIFICATION_READ.value,
    ],
    RoleEnum.SIGNER: [
        PermissionEnum.DECISION_ISSUE.value,
        PermissionEnum.DECISION_READ.value,
        PermissionEnum.ANSWER_READ.value,
        PermissionEnum.CASE_READ.value,
        PermissionEnum.PRECEDENT_WRITE.value,
        PermissionEnum.CASE_CLOSE.value,
        PermissionEnum.NOTIFICATION_READ.value,
    ],
    RoleEnum.ADMIN: [item.value for item in PermissionEnum],
}
