"""Assessment form routes. Confirming the form does not send a legal ticket."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.assessment.schemas import AssessmentPatch, AssessmentView
from src.features.assessment.service import (
    confirm_assessment,
    generate_assessment,
    get_assessment,
    reanalyze_assessment,
    save_assessment,
)
from src.models.users import User

router = APIRouter(prefix="/cases", tags=["Biên bản"])


@router.get("/{case_id}/assessment", response_model=AssessmentView)
async def get_case_assessment(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.ANSWER_READ))],
) -> AssessmentView:
    """Biên bản hiện tại. Frontend chỉ render JSON này."""
    return await get_assessment(session, actor, case_id)


@router.post("/{case_id}/assessment/generate", response_model=AssessmentView)
async def post_generate(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_CHAT))],
) -> AssessmentView:
    """Lập biên bản từ báo cáo đã lưu. Không xác nhận và không gửi pháp chế."""
    return await generate_assessment(session, actor, case_id)


@router.patch("/{case_id}/assessment", response_model=AssessmentView)
async def patch_assessment(
    case_id: UUID,
    payload: AssessmentPatch,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_UPDATE))],
) -> AssessmentView:
    """HR sửa các trường nghiệp vụ. Căn cứ và mã mức không nhận từ client."""
    return await save_assessment(session, actor, case_id, payload)


@router.post("/{case_id}/assessment/save", response_model=AssessmentView)
async def post_save(
    case_id: UUID,
    payload: AssessmentPatch,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_UPDATE))],
) -> AssessmentView:
    """Lưu một phiên bản nháp mới."""
    return await save_assessment(session, actor, case_id, payload)


@router.post("/{case_id}/assessment/confirm", response_model=AssessmentView)
async def post_confirm(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_CONFIRM))],
) -> AssessmentView:
    """HR xác nhận biên bản. Phiếu pháp chế vẫn do HR xác nhận ở bước sau."""
    return await confirm_assessment(session, actor, case_id)


@router.post("/{case_id}/assessment/reanalyze", response_model=AssessmentView)
async def post_reanalyze(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_CHAT))],
) -> AssessmentView:
    """Lập lại biên bản từ tình tiết và căn cứ mới nhất. Phiên bản cũ được giữ."""
    return await reanalyze_assessment(session, actor, case_id)
