"""HTTP surface for opening and reading a case."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.opencase.model.cases import get_case, open_case
from src.features.opencase.model.manage import grant_access, list_access, list_cases, patch_case, reopen_case
from src.features.opencase.schema import (
    AccessGrantRequest,
    AccessListResponse,
    CaseListResponse,
    CasePatchRequest,
    CaseView,
    OpenCaseRequest,
    OpenCaseResponse,
    ReopenRequest,
    ReopenResponse,
)
from src.models.users import User

router = APIRouter(prefix="/cases", tags=["Hồ sơ"])


@router.post("", response_model=OpenCaseResponse, status_code=201)
async def post_case(
    payload: OpenCaseRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_OPEN))],
) -> OpenCaseResponse:
    """Tạo hồ sơ OPEN và hội thoại ACTIVE. Không gọi LLM."""
    return await open_case(session, actor, payload)


@router.get("", response_model=CaseListResponse)
async def read_cases(
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_READ))],
) -> CaseListResponse:
    """Hồ sơ người gọi tạo hoặc được cấp."""
    return await list_cases(session, actor)


@router.get("/{case_id}", response_model=CaseView)
async def read_case(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_READ))],
) -> CaseView:
    """Đọc hồ sơ khi người gọi có quyền xem."""
    return await get_case(session, actor, case_id)


@router.patch("/{case_id}", response_model=CaseView)
async def update_case(
    case_id: UUID,
    payload: CasePatchRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_UPDATE))],
) -> CaseView:
    """Sửa thông tin đầu hồ sơ. Trạng thái không nhận từ client."""
    return await patch_case(session, actor, case_id, payload)


@router.post("/{case_id}/access", response_model=AccessListResponse)
async def post_access(
    case_id: UUID,
    payload: AccessGrantRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_ACCESS))],
) -> AccessListResponse:
    """Cấp hoặc thu hồi quyền trên hồ sơ."""
    return await grant_access(session, actor, case_id, payload)


@router.get("/{case_id}/access", response_model=AccessListResponse)
async def read_access(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_READ))],
) -> AccessListResponse:
    """Danh sách người được cấp quyền."""
    return await list_access(session, actor, case_id)


@router.post("/{case_id}/reopen", response_model=ReopenResponse)
async def post_reopen(
    case_id: UUID,
    payload: ReopenRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_REOPEN))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReopenResponse:
    """Mở lại hồ sơ bị từ chối. Khuyến nghị và biên bản duyệt cũ giữ nguyên."""
    return await reopen_case(session, actor, case_id, payload, idempotency_key)
