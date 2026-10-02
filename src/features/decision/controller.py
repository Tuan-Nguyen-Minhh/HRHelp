"""Signer routes. Sanction type is read from the approved recommendation."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.core.security.guards import require_permissions, require_roles_and_permissions
from src.core.security.rbac import PermissionEnum, RoleEnum
from src.features.decision.model.service import (
    close_case,
    decision_preview,
    issue_decision,
    manager_queue,
    mark_precedent,
)
from src.features.decision.schema import (
    CloseResponse,
    DecisionPreview,
    DecisionView,
    IssueDecisionRequest,
    ManagerQueueResponse,
    PrecedentRequest,
)
from src.models.users import User

router = APIRouter(prefix="/cases", tags=["Quyết định"])
manager_router = APIRouter(tags=["Quản lý"])


@manager_router.get("/manager/queue", response_model=ManagerQueueResponse)
async def get_manager_queue(
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DECISION_READ))],
) -> ManagerQueueResponse:
    """Hồ sơ đã được pháp chế duyệt, hoặc HR chuyển thẳng, đang chờ quản lý."""
    return await manager_queue(session, actor)


@router.get("/{case_id}/decision-preview", response_model=DecisionPreview)
async def get_decision_preview(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DECISION_READ))],
) -> DecisionPreview:
    """Bản xem trước. Mức kỷ luật lấy từ đề xuất đã duyệt."""
    return await decision_preview(session, actor, case_id)


@router.post("/{case_id}/decisions", response_model=DecisionView, status_code=status.HTTP_201_CREATED)
async def post_decision(
    case_id: UUID,
    payload: IssueDecisionRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[
        dict,
        Depends(
            require_roles_and_permissions(
                RoleEnum.SIGNER,
                RoleEnum.MANAGER,
                permissions=(PermissionEnum.DECISION_ISSUE,),
            )
        ),
    ],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DecisionView:
    """Người ký ban hành. Client không được chọn mức khác."""
    return await issue_decision(session, actor, case_id, payload, idempotency_key)


@router.post("/{case_id}/decisions/precedent", response_model=DecisionView)
async def post_precedent(
    case_id: UUID,
    payload: PrecedentRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.PRECEDENT_WRITE))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DecisionView:
    """Đánh dấu quyết định đã ban hành thành tiền lệ."""
    return await mark_precedent(session, actor, case_id, payload, idempotency_key)


@router.post("/{case_id}/close", response_model=CloseResponse)
async def post_close(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_CLOSE))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CloseResponse:
    """Đóng hồ sơ đã có quyết định."""
    return await close_case(session, actor, case_id, idempotency_key)
