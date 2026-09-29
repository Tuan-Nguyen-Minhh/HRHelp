"""HTTP surface for clarifying facts on a case."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.features.clarify.model.turns import confirm_facts, handle_message, list_facts
from src.features.clarify.schema import (
    ConfirmFactsRequest,
    FactListResponse,
    SendMessageRequest,
    TurnResponse,
)
from src.models.users import User

router = APIRouter(prefix="/cases", tags=["Làm rõ tình tiết"])


@router.post("/{case_id}/messages", response_model=TurnResponse)
async def post_message(
    case_id: UUID,
    payload: SendMessageRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TurnResponse:
    """Gửi mô tả hoặc câu trả lời. Chưa chốt mức khi fact còn thiếu."""
    return await handle_message(session, actor, case_id, payload)


@router.post("/{case_id}/facts/confirm", response_model=TurnResponse)
async def post_confirm(
    case_id: UUID,
    payload: ConfirmFactsRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TurnResponse:
    """Xác nhận fact. Khi đủ, đối chiếu văn bản và trả message cho agent đề xuất."""
    return await confirm_facts(session, actor, case_id, payload)


@router.get("/{case_id}/facts", response_model=FactListResponse)
async def read_facts(
    case_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FactListResponse:
    """Form tình tiết của hồ sơ."""
    return await list_facts(session, actor, case_id)
