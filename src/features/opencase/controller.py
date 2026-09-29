"""HTTP surface for opening and reading a case."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.features.opencase.model.cases import get_case, open_case
from src.features.opencase.schema import CaseView, OpenCaseRequest, OpenCaseResponse
from src.models.users import User

router = APIRouter(prefix="/cases", tags=["Hồ sơ"])


@router.post("", response_model=OpenCaseResponse, status_code=201)
async def post_case(
    payload: OpenCaseRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OpenCaseResponse:
    """Tạo hồ sơ OPEN và hội thoại ACTIVE."""
    return await open_case(session, actor, payload)


@router.get("/{case_id}", response_model=CaseView)
async def read_case(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaseView:
    """Đọc hồ sơ của chính người tạo."""
    return await get_case(session, actor, case_id)
