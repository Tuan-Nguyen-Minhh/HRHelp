"""Authenticated chat that needs no case; every conversation belongs to its actor."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.features.standalone_chat.schema import (
    ConversationListResponse,
    StandaloneMessageRequest,
    StandaloneMessagesResponse,
    StandaloneTurnResponse,
)
from src.features.standalone_chat.service import read_conversations, read_messages, send_message
from src.models.users import User

router = APIRouter(prefix="/conversations", tags=["Chat độc lập"])


@router.get("", response_model=ConversationListResponse)
async def list_chats(
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationListResponse:
    return await read_conversations(session, actor)


@router.get("/{conversation_id}/messages", response_model=StandaloneMessagesResponse)
async def get_messages(
    conversation_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StandaloneMessagesResponse:
    return await read_messages(session, actor, conversation_id)


@router.post("/messages", response_model=StandaloneTurnResponse)
async def post_message(
    payload: StandaloneMessageRequest,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StandaloneTurnResponse:
    return await send_message(session, actor, payload)
