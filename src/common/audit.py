"""Append one audit row. Callers commit. There is no update or delete API."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit_logs import AuditLog


async def write_audit(
    session: AsyncSession,
    *,
    case_id: UUID | None,
    actor_id: UUID | None,
    actor_role: str | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None = None,
    before: dict | None = None,
    after: dict | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Record a transition. The row is inserted in the caller's transaction."""
    row = AuditLog(
        case_id=case_id,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        audit_metadata=metadata,
    )
    session.add(row)
    await session.flush()
    return row
