"""Role and permission names.

The enums are the source of truth. Startup copies them into ``roles``,
``permissions`` and ``permission_roles``. A request checks the lists embedded
in the access token, not this map.
"""

from enum import StrEnum


class RoleEnum(StrEnum):
    """The three roles stored on ``users.role``."""

    HR = "HR"
    MANAGER = "MANAGER"
    LEGAL = "LEGAL"


class PermissionEnum(StrEnum):
    """Actions the case routes accept."""

    CASE_OPEN = "case:open"
    CASE_READ = "case:read"
    CASE_CHAT = "case:chat"
    CASE_CONFIRM = "case:confirm"
    ANSWER_READ = "answer:read"


# Seed data only. Runtime authorization reads the token.
DEFAULT_ROLE_PERMISSIONS: dict[RoleEnum, list[str]] = {
    RoleEnum.HR: [item.value for item in PermissionEnum],
    RoleEnum.MANAGER: [item.value for item in PermissionEnum],
    RoleEnum.LEGAL: [],
}
