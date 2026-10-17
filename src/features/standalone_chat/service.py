"""Persist owner-scoped chats and invoke the shared graph with case branches excluded."""

import logging
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.case_graph import build_case_graph
from src.agents.conversation import recent_turns
from src.agents.runs import finish_run, mark_run_failed, start_run
from src.common.clock import utc_now, vietnam_date
from src.common.errors import AppError
from src.features.cite.model.search import search_policies
from src.features.clarify.model.dialogue_context import build_dialogue_context, context_metadata
from src.features.clarify.model.memory import side_context
from src.features.clarify.model.store import NewMessage, add_message, list_messages
from src.features.clarify.schema import MessageView
from src.features.standalone_chat.schema import (
    ConversationListResponse,
    ConversationView,
    StandaloneMessageRequest,
    StandaloneMessagesResponse,
    StandaloneTurnResponse,
)
from src.models.agent_runs import AgentRun
from src.models.conversations import Conversation
from src.models.users import User

logger = logging.getLogger(__name__)


def _owned_chats(actor: User):
    return select(Conversation).where(
        Conversation.user_id == actor.id, Conversation.case_id.is_(None), Conversation.status == "ACTIVE"
    )


async def _require_chat(
    session: AsyncSession, actor: User, conversation_id: UUID, *, lock: bool = False
) -> Conversation:
    query = _owned_chats(actor).where(Conversation.id == conversation_id)
    if lock:
        query = query.with_for_update()
    conversation = await session.scalar(query)
    if conversation is None:
        raise AppError(404, "Không tìm thấy hội thoại.")
    return conversation


async def read_conversations(session: AsyncSession, actor: User) -> ConversationListResponse:
    rows = (await session.scalars(_owned_chats(actor).order_by(Conversation.updated_at.desc()))).all()
    return ConversationListResponse(
        conversations=[
            ConversationView(id=row.id, title=row.title or "Cuộc trò chuyện mới", updated_at=row.updated_at)
            for row in rows
        ]
    )


async def read_messages(session: AsyncSession, actor: User, conversation_id: UUID) -> StandaloneMessagesResponse:
    await _require_chat(session, actor, conversation_id)
    return StandaloneMessagesResponse(
        conversation_id=conversation_id, messages=await _visible_messages(session, conversation_id)
    )


async def _visible_messages(session: AsyncSession, conversation_id: UUID) -> list[MessageView]:
    return [
        MessageView(id=row.id, role=row.role, content=row.content, created_at=row.created_at)
        for row in await list_messages(session, conversation_id)
        if row.role in {"USER", "ASSISTANT"} and not (row.message_metadata or {}).get("internal")
    ]


async def send_message(session: AsyncSession, actor: User, payload: StandaloneMessageRequest) -> StandaloneTurnResponse:
    if payload.conversation_id:
        conversation = await _require_chat(session, actor, payload.conversation_id, lock=True)
        pending = await session.scalar(
            select(AgentRun.id)
            .where(
                AgentRun.conversation_id == conversation.id,
                AgentRun.status == "RUNNING",
                AgentRun.started_at > utc_now() - timedelta(minutes=10),
            )
            .limit(1)
        )
        if pending:
            raise AppError(409, "Trợ lý đang xử lý một tin nhắn trong hội thoại này. Hãy chờ câu trả lời.")
    else:
        conversation = Conversation(
            id=uuid4(), user_id=actor.id, case_id=None, title=payload.content[:100], status="ACTIVE"
        )
        session.add(conversation)
        await session.flush()
    conversation.updated_at = utc_now()
    user_message = await add_message(session, NewMessage(conversation.id, "USER", payload.content))
    run = await start_run(session, conversation.id, user_message.id, "hr-help-standalone")
    run_id, conversation_id = run.id, conversation.id
    await session.commit()
    try:
        rows = await list_messages(session, conversation.id)
        history = recent_turns(
            [
                {"role": row.role, "content": row.content}
                for row in rows
                if row.role in {"USER", "ASSISTANT"} and not (row.message_metadata or {}).get("internal")
            ]
        )
        lookup_date = payload.lookup_date or vietnam_date(utc_now())
        dialogue = await build_dialogue_context(
            session,
            conversation.id,
            payload.content,
            current_message_id=user_message.id,
            chat_scope="standalone",
            rows=rows,
        )
        graph = build_case_graph(lambda query: search_policies(session, query), standalone=True)
        state = await graph.ainvoke(
            {
                "actor_id": actor.id,
                "conversation_id": conversation.id,
                "agent_run_id": run.id,
                "latest_user_message": payload.content,
                "turn_context": history,
                "description": history,
                "incident_date": lookup_date,
                "social_context": await side_context(session, conversation.id),
                "dialogue_context": dialogue,
                "semantic": True,
            }
        )
        kind = state.get("reply_kind") or "clarify"
        metadata = {
            "kind": kind,
            "chat_scope": "standalone",
            "route_trace": state.get("route_trace") or {},
            "lookup_date": lookup_date.isoformat(),
            **context_metadata(dialogue),
        }
        if kind == "general_chat":
            metadata.update(context_scope="general", include_in_general_context=state.get("safety_action") == "allow")
        elif kind == "system_help":
            metadata["context_scope"] = "system_help"
        if state.get("help_topic_ids"):
            metadata["help_topic_ids"] = state["help_topic_ids"]
        if kind == "clarify" and state.get("clarification_question"):
            prior = (state.get("social_context") or {}).get("routing_clarification") or {}
            metadata["routing_clarification"] = {
                "original_question": prior.get("original_question") or payload.content,
                "origin_message_id": prior.get("origin_message_id") or str(user_message.id),
            }
        user_message.message_metadata = metadata.copy()
        assistant = await add_message(session, NewMessage(conversation.id, "ASSISTANT", state["question"], metadata))
        finish_run(run, assistant.id)
        conversation.updated_at = utc_now()
        await session.commit()
        return StandaloneTurnResponse(
            conversation_id=conversation.id,
            messages=await _visible_messages(session, conversation.id),
            agent_run_id=run.id,
            reply_kind=kind,
            lookup_date=lookup_date,
        )
    except Exception as exc:
        await session.rollback()
        await mark_run_failed(session, run_id, type(exc).__name__)
        await session.commit()
        logger.exception("standalone chat failed run_id=%s", run_id)
        if isinstance(exc, AppError):
            exc.details["conversation_id"] = str(conversation_id)
            raise
        raise AppError(
            503,
            "Chưa xử lý được câu trả lời. Tin nhắn đã lưu trong lịch sử; bạn có thể thử lại.",
            details={"conversation_id": str(conversation_id)},
        ) from exc
