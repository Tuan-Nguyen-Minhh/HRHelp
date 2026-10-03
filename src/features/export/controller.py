"""Export routes. They read stored rows and do not rerun an agent."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.access import require_case
from src.common.deps import get_actor, get_session
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.answer.model.answers import load_stored
from src.features.answer.model.case_tools import CASE_TOOL_SCHEMAS, CaseToolCall, call_case_tool
from src.features.export.model import export_assessment, export_decision, export_ticket
from src.models.users import User

router = APIRouter(prefix="/cases", tags=["Xuất hồ sơ"])


@router.get("/{case_id}/export/assessment")
async def get_assessment_export(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.ANSWER_READ))],
    format: Annotated[Literal["json", "markdown", "docx"], Query()] = "json",
) -> dict:
    return await export_assessment(session, actor, case_id, format)


@router.get("/{case_id}/export/ticket")
async def get_ticket_export(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.ANSWER_READ))],
    format: Annotated[Literal["json", "markdown", "docx"], Query()] = "json",
) -> dict:
    return await export_ticket(session, actor, case_id, format)


@router.get("/{case_id}/export/decision")
async def get_decision_export(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_READ))],
    format: Annotated[Literal["json", "markdown", "docx"], Query()] = "json",
) -> dict:
    return await export_decision(session, actor, case_id, format)


@router.get("/case-tools")
async def get_case_tool_schemas(
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.ANSWER_READ))],
) -> dict:
    """MCP-style tool schemas for case document generation."""
    return {"tools": list(CASE_TOOL_SCHEMAS)}


@router.post("/{case_id}/case-tools/call")
async def post_case_tool_call(
    case_id: UUID,
    payload: CaseToolCall,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.ANSWER_READ))],
) -> dict:
    """Invoke one safe MCP-style case document tool."""
    case = await require_case(session, case_id, actor)
    answer = await load_stored(session, case)
    result = await call_case_tool(case, answer, payload)
    return result.model_dump()
