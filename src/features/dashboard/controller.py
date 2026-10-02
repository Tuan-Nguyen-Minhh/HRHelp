"""Dashboard routes. Each query is limited to cases the caller may see."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.dashboard.model import cases_breakdown, processing_time, sanctions, summary
from src.features.dashboard.schema import CasesResponse, ProcessingTimeResponse, SanctionsResponse, SummaryResponse
from src.models.users import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DASHBOARD_READ))],
) -> SummaryResponse:
    return await summary(session, actor)


@router.get("/cases", response_model=CasesResponse)
async def get_cases(
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DASHBOARD_READ))],
) -> CasesResponse:
    return await cases_breakdown(session, actor)


@router.get("/processing-time", response_model=ProcessingTimeResponse)
async def get_processing_time(
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DASHBOARD_READ))],
) -> ProcessingTimeResponse:
    return await processing_time(session, actor)


@router.get("/sanctions", response_model=SanctionsResponse)
async def get_sanctions(
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DASHBOARD_READ))],
) -> SanctionsResponse:
    return await sanctions(session, actor)
