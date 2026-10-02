"""Routes for the legal queue. They do not choose a sanction."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.legal_review.model.service import latest_review, review_pack, review_queue, submit_review
from src.features.legal_review.schema import QueueResponse, ReviewPack, ReviewRequest, ReviewView
from src.models.users import User

router = APIRouter(tags=["Pháp chế"])


@router.get("/legal/reviews/queue", response_model=QueueResponse)
async def get_queue(
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.LEGAL_REVIEW))],
) -> QueueResponse:
    """Hàng chờ mọi hồ sơ PENDING_LEGAL. Tài khoản pháp chế đều thấy phiếu HR vừa gửi."""
    return await review_queue(session, actor)


@router.get("/cases/{case_id}/review-pack", response_model=ReviewPack)
async def get_review_pack(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.LEGAL_REVIEW))],
) -> ReviewPack:
    """Gói đọc: báo cáo và nháp đã lưu."""
    return await review_pack(session, actor, case_id)


@router.get("/cases/{case_id}/reviews/latest", response_model=ReviewView)
async def get_latest_review(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_READ))],
) -> ReviewView:
    """Kết luận pháp chế gần nhất, để HR đọc yêu cầu xử lý lại."""
    return await latest_review(session, actor, case_id)


@router.post("/cases/{case_id}/reviews", response_model=ReviewView)
async def post_review(
    case_id: UUID,
    payload: ReviewRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.LEGAL_REVIEW))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReviewView:
    """Pháp chế duyệt hoặc từ chối. Không sửa mức, fact, hay trích dẫn."""
    return await submit_review(session, actor, case_id, payload, idempotency_key)
