"""Read the layered answer of a case."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.access import require_case
from src.common.deps import get_actor, get_session
from src.common.errors import AppError
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.answer.model.answers import load
from src.features.answer.model.send import escalate_to_manager, list_legal_officers, send_ticket
from src.features.answer.schema import AnswerView, LegalOfficer, LegalOfficerList, SendTicketRequest
from src.models.users import User

router = APIRouter(prefix="/cases", tags=["Câu trả lời"])
officers_router = APIRouter(tags=["Câu trả lời"])


@officers_router.get("/legal-officers", response_model=LegalOfficerList)
async def get_legal_officers(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_CHAT))],
) -> LegalOfficerList:
    """Email của các tài khoản pháp chế đang hoạt động."""
    rows = await list_legal_officers(session)
    return LegalOfficerList(users=[LegalOfficer(email=row.email, full_name=row.full_name) for row in rows])


@router.get("/{case_id}/answer", response_model=AnswerView)
async def read_answer(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.ANSWER_READ))],
) -> AnswerView:
    """Đọc báo cáo hiện tại: đề xuất, bản thảo và yêu cầu đẩy phiếu."""
    case = await require_case(session, case_id, actor)
    view = await load(session, case)
    if view is None:
        raise AppError(404, "Hồ sơ chưa có câu trả lời.")
    return view


@router.post("/{case_id}/ticket", response_model=AnswerView)
async def post_ticket(
    case_id: UUID,
    payload: SendTicketRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_CHAT))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AnswerView:
    """HR đã xem phiếu và chọn email pháp chế sẽ nhận phiếu."""
    return await send_ticket(session, actor, case_id, payload.legal_code, idempotency_key)


@router.post("/{case_id}/escalate", response_model=AnswerView)
async def post_escalate(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_CHAT))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AnswerView:
    """HR xác nhận xử lý luôn và đẩy hồ sơ cho quản lý duyệt lần cuối."""
    return await escalate_to_manager(session, actor, case_id, idempotency_key)
