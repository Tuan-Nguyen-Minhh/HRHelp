"""Exercise graph validation and SQL persistence; synthetic rows are rolled back."""

import os
from dataclasses import asdict
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.core.config import settings
from src.features.clarify.model import turns
from src.features.clarify.model.catalog import FactSpec
from src.features.clarify.model.decision import ClarifyDecision, ExtractedFact, RequestedAction, UserIntent
from src.features.clarify.model.intent import IntentDecision, IntentFallback, IntentResult, Route
from src.features.clarify.model.planner import PlannerResult
from src.features.clarify.model.store import NewMessage, add_message
from src.models.case_facts import CaseFact
from src.models.cases import Case
from src.models.conversation_memories import ConversationMemory
from src.models.conversations import Conversation
from src.models.users import User


@pytest.mark.skipif(os.getenv("P029_RUN_DB_TESTS") != "1", reason="Requires migrated local PostgreSQL")
@pytest.mark.asyncio
async def test_answered_procedures_are_saved_and_not_missing_on_next_projection(monkeypatch, dialogue_model):
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI)
    uid, cid, conversation_id = uuid4(), uuid4(), uuid4()
    specs = [
        FactSpec("minutes_made", "Biên bản vụ việc", "Vụ việc đã được lập biên bản chưa?"),
        FactSpec("explanation_requested", "Yêu cầu giải trình", "Đã yêu cầu nhân viên giải trình chưa?"),
    ]
    message = (
        "Biên bản vụ việc: Đã lập biên bản ghi nhận sự việc vi phạm quy định bảo mật thông tin.\n\n"
        "Yêu cầu giải trình: Đã gửi văn bản yêu cầu nhân viên giải trình (thời hạn phản hồi trong 03 ngày làm việc)."
    )
    decision = ClarifyDecision(
        family="confidentiality_breach",
        family_confidence=0.99,
        extracted_facts=[
            ExtractedFact(key=spec.key, value="true", evidence=proof, confidence=0.99, ambiguous=False)
            for spec, proof in zip(specs, message.split("\n\n"), strict=True)
        ],
        user_intent=UserIntent.PROVIDE_FACTS,
        requested_action=RequestedAction.COMPLETE_FACTS,
        confidence=0.99,
    )
    monkeypatch.setattr(
        "src.agents.case_graph.route_turn",
        AsyncMock(
            return_value=IntentResult(
                IntentDecision(
                    route=Route.FACT_PLANNER, intent_label="provide_facts", requires_fact_planner=True, confidence=0.99
                ),
                IntentFallback.NONE,
                None,
                1,
                "test",
            )
        ),
    )
    monkeypatch.setattr(
        "src.features.clarify.model.graph.plan_turn",
        AsyncMock(return_value=PlannerResult(decision, False, None, 1, "test")),
    )
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
                ) as session:
                    session.add(
                        User(id=uid, email=f"procedural-{uid}@example.invalid", password_hash="test", role="HR")
                    )
                    await session.flush()
                    case = Case(
                        id=cid,
                        created_by=uid,
                        case_code=f"TEST-PROCEDURAL-{cid}",
                        description="Synthetic confidentiality incident",
                        status="OPEN",
                    )
                    session.add(case)
                    await session.flush()
                    session.add(Conversation(id=conversation_id, case_id=cid, user_id=uid, status="ACTIVE"))
                    await session.flush()
                    memory = ConversationMemory(
                        conversation_id=conversation_id,
                        pending_action="draft_minutes",
                        pending_fact_keys=[spec.key for spec in specs],
                        summary="Original working state",
                        working_state={
                            "version": 1,
                            "family": "confidentiality_breach",
                            "specs": [asdict(spec) for spec in specs],
                        },
                    )
                    session.add(memory)
                    await add_message(
                        session, NewMessage(conversation_id, "ASSISTANT", "\n".join(spec.question for spec in specs))
                    )
                    source = await add_message(session, NewMessage(conversation_id, "USER", message))
                    await session.commit()
                    plan, handoff = await turns._planned(
                        session,
                        case,
                        conversation_id,
                        source.id,
                        semantic=True,
                        actor_id=uid,
                        latest_user_message=message,
                    )
                    assert plan.locked and plan.missing_keys == [] and handoff is None
                    facts = (await session.scalars(select(CaseFact).where(CaseFact.case_id == cid))).all()
                    assert {fact.fact_key: fact.fact_value for fact in facts} == {
                        "minutes_made": "true",
                        "explanation_requested": "true",
                    }
                    assert all(
                        fact.confirmed and fact.confirmed_by == uid and fact.source_message_id == source.id
                        for fact in facts
                    )
                    projection, _ = await turns._plan(session, case, conversation_id, semantic=True)
                    assert projection.locked and projection.missing_keys == []
                    assert memory.summary == "Original working state" and memory.pending_action == "draft_minutes"
                    assert case.status == "OPEN"
            finally:
                await transaction.rollback()
        async with AsyncSession(engine) as verify:
            assert await verify.get(Case, cid) is None
    finally:
        await engine.dispose()
