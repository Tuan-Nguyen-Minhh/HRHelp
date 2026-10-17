"""Real API/storage tests, with all synthetic rows rolled back at the end."""

import json
import os
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.common.deps import get_session
from src.core.config import settings
from src.core.security.auth_handler import AuthHandler
from src.core.security.tokens import claims_for_role
from src.features.clarify.model.general_chat import ChatReply
from src.features.clarify.model.intent import IntentDecision, IntentFallback, IntentResult, Route
from src.features.clarify.model.system_help import HelpTopic
from src.main import app
from src.models.agent_runs import AgentRun
from src.models.cases import Case
from src.models.conversations import Conversation
from src.models.messages import Message
from src.models.users import User


@pytest.mark.skipif(os.getenv("P029_RUN_DB_TESTS") != "1", reason="Requires migrated local PostgreSQL")
@pytest.mark.asyncio
async def test_chat_storage_ownership_history_and_failure_without_a_case(
    monkeypatch, approved_help_reply, dialogue_model
):
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI)
    uid, other_uid, case_id, case_conversation_id = (uuid4() for _ in range(4))
    old_overrides = app.dependency_overrides.copy()
    route = AsyncMock()
    chat = AsyncMock(return_value=ChatReply("Chào bạn!", "allow"))
    monkeypatch.setattr("src.agents.case_graph.route_turn", route)
    monkeypatch.setattr("src.agents.case_graph.answer_general_chat", chat)
    forbidden = AsyncMock(side_effect=AssertionError("Standalone may not call the planner/extractor"))
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", forbidden)
    monkeypatch.setattr("src.agents.case_graph.extract_node", forbidden)

    def decision(selected, **kwargs):
        route.return_value = IntentResult(
            IntentDecision(route=selected, intent_label="test", confidence=0.99, **kwargs),
            IntentFallback.NONE,
            None,
            1,
            "test",
        )

    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False, autoflush=False
                ) as session:
                    session.add_all(
                        [
                            User(id=uid, email=f"chat-{uid}@example.invalid", password_hash="test", role="HR"),
                            User(
                                id=other_uid, email=f"chat-{other_uid}@example.invalid", password_hash="test", role="HR"
                            ),
                        ]
                    )
                    await session.flush()
                    session.add(Case(id=case_id, created_by=uid, case_code=f"TEST-CHAT-{case_id}", status="OPEN"))
                    await session.flush()
                    session.add(Conversation(id=case_conversation_id, user_id=uid, case_id=case_id, status="ACTIVE"))
                    await session.commit()

                    async def db():
                        yield session

                    app.dependency_overrides[get_session] = db

                    def headers(actor_id):
                        token = AuthHandler.create_access_token(
                            {"user_id": str(actor_id), "is_active": True}, **claims_for_role("HR")
                        )
                        return {"Authorization": f"Bearer {token}"}

                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        base = "/api/v1/conversations"
                        decision(Route.GENERAL_CHAT)
                        first = await client.post(
                            f"{base}/messages", headers=headers(uid), json={"content": "Chào bạn"}
                        )
                        assert first.status_code == 200, first.text
                        data = first.json()
                        cid = data["conversation_id"]
                        conversation = await session.get(Conversation, UUID(cid))
                        assert conversation.case_id is None and conversation.user_id == uid
                        assert [m["role"] for m in data["messages"]] == ["USER", "ASSISTANT"]

                        followup = await client.post(
                            f"{base}/messages", headers=headers(uid), json={"content": "Cảm ơn", "conversation_id": cid}
                        )
                        assert followup.status_code == 200, followup.text
                        assert len(followup.json()["messages"]) == 4
                        assert chat.call_args.args[1]["social_context"]["general_messages"][0]["content"] == "Chào bạn"

                        listed = (await client.get(base, headers=headers(uid))).json()["conversations"]
                        assert [row["id"] for row in listed] == [cid]
                        assert (await client.get(base, headers=headers(other_uid))).json()["conversations"] == []
                        for inaccessible in (cid, str(case_conversation_id), str(uuid4())):
                            actor_id = other_uid if inaccessible == cid else uid
                            assert (
                                await client.get(f"{base}/{inaccessible}/messages", headers=headers(actor_id))
                            ).status_code == 404
                            assert (
                                await client.post(
                                    f"{base}/messages",
                                    headers=headers(actor_id),
                                    json={"content": "test", "conversation_id": inaccessible},
                                )
                            ).status_code == 404

                        decision(Route.POLICY_QA)
                        retrieval = AsyncMock(return_value=[])
                        monkeypatch.setattr("src.features.standalone_chat.service.search_policies", retrieval)
                        policy = await client.post(
                            f"{base}/messages",
                            headers=headers(uid),
                            json={"content": "Quy định thế nào?", "conversation_id": cid, "lookup_date": "2025-03-01"},
                        )
                        assert policy.status_code == 200, policy.text
                        assert retrieval.call_args.args[1].incident_date.isoformat() == "2025-03-01"

                        decision(Route.WORKFLOW_ACTION, requested_action="draft_minutes", requires_fact_planner=True)
                        minutes = await client.post(
                            f"{base}/messages",
                            headers=headers(uid),
                            json={"content": "Lập biên bản", "conversation_id": cid},
                        )
                        assert minutes.status_code == 200, minutes.text
                        assert minutes.json()["reply_kind"] == "case_required"

                        decision(Route.EXTERNAL_RESEARCH)
                        monkeypatch.setattr(
                            "src.agents.case_graph.research_external",
                            AsyncMock(side_effect=RuntimeError("test failure")),
                        )
                        failed = await client.post(
                            f"{base}/messages",
                            headers=headers(uid),
                            json={"content": "Tra web", "conversation_id": cid},
                        )
                        assert failed.status_code == 503, failed.text
                        assert failed.json()["error"]["details"]["conversation_id"] == cid
                        runs = (
                            await session.scalars(select(AgentRun).where(AgentRun.conversation_id == UUID(cid)))
                        ).all()
                        assert sorted(run.status for run in runs) == [
                            "FAILED",
                            "SUCCEEDED",
                            "SUCCEEDED",
                            "SUCCEEDED",
                            "SUCCEEDED",
                        ]
                        decision(Route.GENERAL_CHAT)
                        retry = await client.post(
                            f"{base}/messages",
                            headers=headers(uid),
                            json={"content": "Chào lại", "conversation_id": cid},
                        )
                        assert retry.status_code == 200, retry.text
                        read = await client.get(f"{base}/{cid}/messages", headers=headers(uid))
                        assert len(read.json()["messages"]) == 11

                        # A failed first turn still exposes the saved chat for a retry in the same history.
                        decision(Route.EXTERNAL_RESEARCH)
                        first_failed = await client.post(
                            f"{base}/messages", headers=headers(uid), json={"content": "Tra web trong chat mới"}
                        )
                        assert first_failed.status_code == 503, first_failed.text
                        failed_cid = first_failed.json()["error"]["details"]["conversation_id"]
                        first_history = await client.get(f"{base}/{failed_cid}/messages", headers=headers(uid))
                        assert len(first_history.json()["messages"]) == 1
                        decision(Route.GENERAL_CHAT)
                        recovered = await client.post(
                            f"{base}/messages",
                            headers=headers(uid),
                            json={"content": "Thử lại", "conversation_id": failed_cid},
                        )
                        assert recovered.status_code == 200, recovered.text
                        assert len(recovered.json()["messages"]) == 3
                        decision(Route.SYSTEM_HELP, help_topic_ids=[HelpTopic.MINUTES_START])
                        usage_question = "Tôi muốn lập biên bản thì bắt đầu ở đâu?"
                        usage = await client.post(
                            f"{base}/messages",
                            headers=headers(uid),
                            json={"content": usage_question, "conversation_id": cid},
                        )
                        assert usage.status_code == 200, usage.text
                        for row in usage.json()["messages"][-2:]:
                            saved = await session.get(Message, UUID(row["id"]))
                            assert saved.message_metadata["context_scope"] == "system_help"
                        followup_help = await client.post(
                            f"{base}/messages",
                            headers=headers(uid),
                            json={"content": "Tôi đã vào hồ sơ, tiếp theo làm gì?", "conversation_id": cid},
                        )
                        assert followup_help.status_code == 200, followup_help.text
                        formatting_state = approved_help_reply.call_args.args[2]
                        assert formatting_state["social_context"]["help_messages"][0] == {
                            "role": "USER",
                            "content": usage_question,
                        }
                        assert usage_question in formatting_state["turn_context"]
                        assert approved_help_reply.await_count == 2
                        assert formatting_state["dialogue_context"]["status"] == "ready"
                        assert (
                            formatting_state["dialogue_context"]["analysis"]["interpreted_question"]["text"]
                            == "Tôi đã vào hồ sơ, tiếp theo làm gì?"
                        )
                        assistant_row = await session.get(Message, UUID(followup_help.json()["messages"][-1]["id"]))
                        checkpoint = assistant_row.message_metadata["dialogue_context"]
                        assert checkpoint["through_message_id"] == followup_help.json()["messages"][-2]["id"]
                        assert "status" not in checkpoint and "source_turns" not in checkpoint
                        assert any(
                            json.loads(call.args[0][1]["content"])["previous_context"]
                            for call in dialogue_model.call_args_list
                        )
                        assert (
                            await session.scalar(select(func.count()).select_from(Case).where(Case.created_by == uid))
                            == 1
                        )
                        forbidden.assert_not_awaited()
            finally:
                await transaction.rollback()
        async with AsyncSession(engine) as verify:
            assert await verify.get(User, uid) is None
            assert await verify.get(Case, case_id) is None
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
        await engine.dispose()
