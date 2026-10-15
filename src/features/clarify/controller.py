"""HTTP surface for clarifying facts on a case."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.access import require_case
from src.common.deps import get_actor, get_session
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.clarify.model.store import list_messages
from src.features.clarify.model.turns import confirm_facts, handle_message, list_facts
from src.features.clarify.schema import (
    ConfirmFactsRequest,
    FactListResponse,
    MessageListResponse,
    MessageView,
    SendMessageRequest,
    TurnResponse,
)
from src.features.opencase.model.cases import active_conversation
from src.models.users import User

router = APIRouter(prefix="/cases", tags=["Làm rõ tình tiết"])


@router.post("/{case_id}/messages", response_model=TurnResponse)
async def post_message(
    case_id: UUID,
    payload: SendMessageRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_CHAT))],
) -> TurnResponse:
    """Gửi mô tả hoặc câu trả lời. Chưa chốt mức khi fact còn thiếu."""
    return await handle_message(session, actor, case_id, payload)


@router.get("/{case_id}/messages", response_model=MessageListResponse)
async def read_messages(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_READ))],
) -> MessageListResponse:
    """Đọc hội thoại đã lưu. Không chạy lại agent."""
    case = await require_case(session, case_id, actor)
    conversation = await active_conversation(session, case.id)
    if conversation is None:
        return MessageListResponse(case_id=case.id, conversation_id=None, messages=[])
    rows = await list_messages(session, conversation.id)
    return MessageListResponse(
        case_id=case.id,
        conversation_id=conversation.id,
        messages=[
            MessageView(id=row.id, role=row.role, content=row.content, created_at=row.created_at)
            for row in rows
            if not (row.message_metadata or {}).get("internal")
        ],
    )


@router.post("/{case_id}/facts/confirm", response_model=TurnResponse)
async def post_confirm(
    case_id: UUID,
    payload: ConfirmFactsRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_CONFIRM))],
) -> TurnResponse:
    """Xác nhận fact. Khi đủ, đối chiếu văn bản và trả message cho agent đề xuất."""
    return await confirm_facts(session, actor, case_id, payload)


@router.get("/{case_id}/facts", response_model=FactListResponse)
async def read_facts(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.CASE_READ))],
) -> FactListResponse:
    """Form tình tiết của hồ sơ."""
    return await list_facts(session, actor, case_id)
