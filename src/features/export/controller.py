"""Export routes. They read stored rows and do not rerun an agent."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.export.model import export_assessment, export_decision, export_ticket
from src.models.users import User

router = APIRouter(prefix="/cases", tags=["Xuất hồ sơ"])


@router.get("/{case_id}/export/assessment")
async def get_assessment_export(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.ANSWER_READ))],
    format: Annotated[Literal["json", "markdown"], Query()] = "json",
) -> dict:
    return await export_assessment(session, actor, case_id, format)


@router.get("/{case_id}/export/ticket")
async def get_ticket_export(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.ANSWER_READ))],
    format: Annotated[Literal["json", "markdown"], Query()] = "json",
) -> dict:
    return await export_ticket(session, actor, case_id, format)


@router.get("/{case_id}/export/decision")
async def get_decision_export(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_READ))],
    format: Annotated[Literal["json", "markdown"], Query()] = "json",
) -> dict:
    return await export_decision(session, actor, case_id, format)
