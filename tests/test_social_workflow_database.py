"""Real API and PostgreSQL tests. Every synthetic row is rolled back."""

import os
from dataclasses import asdict
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.common.clock import utc_now
from src.common.deps import get_session
from src.core.config import settings
from src.core.security.auth_handler import AuthHandler
from src.core.security.tokens import claims_for_role
from src.features.clarify.model import intent, turns
from src.features.clarify.model.catalog import FactSpec
from src.features.clarify.model.general_chat import ChatReply
from src.features.clarify.model.intent import IntentDecision, RecheckDecision, Route
from src.features.clarify.model.memory import build_turn_context, side_context
from src.features.clarify.model.system_help import HelpTopic
from src.main import app
from src.models.case_facts import CaseFact
from src.models.cases import Case
from src.models.conversation_memories import ConversationMemory
from src.models.conversations import Conversation
from src.models.messages import Message
from src.models.recommendations import Recommendation
from src.models.users import User


@pytest.mark.skipif(os.getenv("P029_RUN_DB_TESTS") != "1", reason="Requires local migrated PostgreSQL")
@pytest.mark.asyncio
async def test_help_recheck_clarification_and_social_turns_preserve_real_case(monkeypatch):
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI)
    suffix = uuid4().hex
    uid, cid, conversation_id, report_id = (uuid4() for _ in range(4))
    old_overrides = app.dependency_overrides.copy()
    help_decision = IntentDecision(
        route=Route.SYSTEM_HELP, intent_label="ask_authority", confidence=0.98, help_topic_ids=[HelpTopic.AUTHORITY]
    )
    general_decision = IntentDecision(route=Route.GENERAL_CHAT, intent_label="meal_idea", confidence=0.98)
    first = AsyncMock(side_effect=[help_decision, help_decision, help_decision, general_decision])
    question = "Bạn muốn hỏi về quyền của AI hay yêu cầu duyệt hồ sơ?"
    recheck = AsyncMock(
        side_effect=[
            RecheckDecision(status="confirmed", decision=help_decision),
            RecheckDecision(status="needs_clarification", clarification_question=question),
            RecheckDecision(status="confirmed", decision=general_decision),
        ]
    )
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(intent, "_complete", first)
    monkeypatch.setattr(intent, "_recheck", recheck)
    monkeypatch.setattr(
        "src.agents.case_graph.answer_general_chat",
        AsyncMock(return_value=ChatReply("Bạn thích món nước hay món khô?", "allow")),
    )
    forbidden = AsyncMock(side_effect=AssertionError("Side turns cannot persist facts"))
    monkeypatch.setattr(turns, "_persist_extracted", forbidden)
    try:
        async with engine.connect() as connection:
            outer = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False, autoflush=False
                ) as session:
                    session.add(
                        User(id=uid, email=f"social-{suffix}@example.invalid", password_hash="test-only", role="HR")
                    )
                    await session.flush()
                    session.add(
                        Case(
                            id=cid,
                            created_by=uid,
                            case_code=f"TEST-SOCIAL-{suffix}",
                            status="ANALYZED",
                            employee_name="Synthetic employee",
                            description="Synthetic saved narrative",
                        )
                    )
                    await session.flush()
                    session.add(Conversation(id=conversation_id, case_id=cid, user_id=uid, status="ACTIVE"))
                    session.add(
                        Recommendation(
                            id=report_id, case_id=cid, recommendation="Original saved report", status="DRAFT"
                        )
                    )
                    session.add(
                        CaseFact(
                            case_id=cid,
                            fact_key="site_location",
                            fact_value="Kho A",
                            confirmed=True,
                            confirmed_by=uid,
                            confirmed_at=utc_now(),
                        )
                    )
                    await session.flush()
                    specs = [
                        FactSpec("site_location", "Địa điểm", "Ở đâu?"),
                        FactSpec("witness", "Nhân chứng", "Ai chứng kiến?"),
                    ]
                    memory = ConversationMemory(
                        conversation_id=conversation_id,
                        summary="Original business memory",
                        pending_action="draft_minutes",
                        pending_fact_keys=["witness"],
                        open_questions=["Ai chứng kiến?"],
                        working_state={"version": 1, "family": "custom", "specs": [asdict(s) for s in specs]},
                    )
                    session.add(memory)
                    await session.commit()

                    async def db():
                        yield session

                    app.dependency_overrides[get_session] = db
                    token = AuthHandler.create_access_token(
                        {"user_id": str(uid), "is_active": True}, **claims_for_role("HR")
                    )
                    headers = {"Authorization": f"Bearer {token}"}
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        root = f"/api/v1/cases/{cid}/messages"
                        help_response = await client.post(
                            root, headers=headers, json={"content": "AI có quyền phê duyệt không?"}
                        )
                        assert help_response.status_code == 200, help_response.text
                        assert help_response.json()["reply_kind"] == "system_help"
                        assert help_response.json()["state_update"] == "preserve"
                        ambiguous = await client.post(
                            root, headers=headers, json={"content": "Bạn xử lý phê duyệt giúp tôi"}
                        )
                        assert ambiguous.status_code == 200, ambiguous.text
                        assert ambiguous.json()["assistant_message"] == question
                        assert (await side_context(session, conversation_id))["routing_clarification"][
                            "original_question"
                        ] == "Bạn xử lý phê duyệt giúp tôi"
                        followup = await client.post(
                            root, headers=headers, json={"content": "Tôi chỉ hỏi quyền của AI"}
                        )
                        assert followup.status_code == 200, followup.text
                        assert followup.json()["reply_kind"] == "system_help"
                        prompt = first.call_args_list[2].args[0][1]["content"]
                        assert "Bạn xử lý phê duyệt giúp tôi" in prompt and "Tôi chỉ hỏi quyền của AI" in prompt
                        social = await client.post(root, headers=headers, json={"content": "Hôm nay ăn gì?"})
                        assert social.status_code == 200, social.text
                        assert social.json()["reply_kind"] == "general_chat"
                        assert social.json()["case_status"] == "ANALYZED"
                    assert recheck.await_count == 3
                    assert (await session.get(Case, cid)).status == "ANALYZED"
                    assert (await session.get(Recommendation, report_id)).recommendation == "Original saved report"
                    assert memory.summary == "Original business memory"
                    assert memory.pending_action == "draft_minutes" and memory.pending_fact_keys == ["witness"]
                    assert memory.open_questions == ["Ai chứng kiến?"]
                    facts = (await session.scalars(select(CaseFact).where(CaseFact.case_id == cid))).all()
                    assert len(facts) == 1 and facts[0].confirmed and facts[0].fact_value == "Kho A"
                    messages = (
                        await session.scalars(select(Message).where(Message.conversation_id == conversation_id))
                    ).all()
                    assert len(messages) == 8
                    assert all(
                        m.message_metadata.get("context_scope") in {"system_help", "general", "routing_clarification"}
                        for m in messages
                    )
                    context = await build_turn_context(session, conversation_id, "Original narrative", {})
                    assert "Hôm nay ăn gì" not in context and "AI có quyền phê duyệt" not in context
                    forbidden.assert_not_awaited()
            finally:
                await outer.rollback()
        async with AsyncSession(engine) as verify:
            assert await verify.get(Case, cid) is None
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
        await engine.dispose()
