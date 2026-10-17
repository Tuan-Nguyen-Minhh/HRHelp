"""Standalone mode shares responders but cannot execute case/fact workflows."""

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.agents.case_graph import build_case_graph
from src.features.clarify.model.general_chat import ChatReply
from src.features.clarify.model.intent import IntentDecision, IntentFallback, IntentResult, Route, render_intent_prompt
from src.features.clarify.model.system_help import HelpTopic
from src.features.external_research.model.tool import ExternalResearchResult
from src.features.standalone_chat.schema import StandaloneMessageRequest

pytestmark = pytest.mark.usefixtures("approved_help_reply")


def routed(monkeypatch, route, **kwargs):
    decision = IntentDecision(route=route, intent_label="test", confidence=0.99, **kwargs)
    router = AsyncMock(return_value=IntentResult(decision, IntentFallback.NONE, None, 1, "test"))
    monkeypatch.setattr("src.agents.case_graph.route_turn", router)
    return router


def forbid_facts(monkeypatch):
    forbidden = AsyncMock(side_effect=AssertionError("Standalone chat must never extract facts"))
    monkeypatch.setattr("src.agents.case_graph.extract_node", forbidden)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", forbidden)
    return forbidden


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["draft_minutes", "create_ticket_preview", "send_to_legal", "show_assessment"])
@pytest.mark.parametrize("entry", [{}, {"step": "cite", "advance": True}, {"step": "open", "semantic": False}])
async def test_workflows_cannot_enter_extraction_or_downstream_nodes(monkeypatch, action, entry):
    routed(
        monkeypatch, Route.WORKFLOW_ACTION, requested_action=action, requires_fact_planner=action != "show_assessment"
    )
    facts = forbid_facts(monkeypatch)
    retrieval = AsyncMock(side_effect=AssertionError("Cannot retrieve for a case workflow"))
    graph = build_case_graph(retrieval, standalone=True)
    assert not {"extract", "ask", "retrieve", "handoff", "open"} & graph.get_graph().nodes.keys()
    result = await graph.ainvoke({"latest_user_message": "Thực hiện giúp tôi", **entry})
    assert result["reply_kind"] == "case_required"
    assert result["requested_action"] == ""
    assert "hồ sơ" in result["question"]
    assert not result.get("handoff")
    facts.assert_not_awaited()
    retrieval.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", [Route.FACT_PLANNER, Route.CASE_QA])
async def test_narrative_and_memory_use_raw_conversation_without_extracting(monkeypatch, route):
    router = routed(monkeypatch, route, requires_fact_planner=route == Route.FACT_PLANNER)
    facts = forbid_facts(monkeypatch)
    answer = AsyncMock(return_value="Mình đã hiểu nội dung bạn vừa chia sẻ.")
    monkeypatch.setattr("src.agents.case_graph.answer_case_question", answer)
    result = await build_case_graph(AsyncMock(), standalone=True).ainvoke(
        {
            "latest_user_message": "Nhân viên nghỉ 5 ngày",
            "turn_context": "USER: nghỉ 5 ngày",
        }
    )
    assert result["question"] == answer.return_value
    assert answer.call_args.args[1]["chat_scope"] == "standalone"
    assert router.call_args.args[0]["chat_scope"] == "standalone"
    facts.assert_not_awaited()


@pytest.mark.asyncio
async def test_internal_policy_keeps_shared_retrieval_and_selected_date(monkeypatch):
    routed(monkeypatch, Route.POLICY_QA)
    facts = forbid_facts(monkeypatch)
    answer = AsyncMock(return_value="Căn cứ được tra cứu.")
    monkeypatch.setattr("src.agents.case_graph.answer_policy_question", answer)
    retrieve = AsyncMock(return_value=[])
    result = await build_case_graph(retrieve, standalone=True).ainvoke(
        {
            "latest_user_message": "Quy định thế nào?",
            "incident_date": date(2025, 3, 1),
            "agent_run_id": uuid4(),
            "description": "USER: nghỉ không phép 5 ngày",
        }
    )
    query = retrieve.call_args.args[0]
    assert query.incident_date == date(2025, 3, 1)
    assert "nghỉ không phép" in query.description
    assert result["question"] == answer.return_value
    assert not result.get("handoff")
    facts.assert_not_awaited()


@pytest.mark.asyncio
async def test_external_research_uses_existing_tool_and_answer(monkeypatch):
    routed(monkeypatch, Route.EXTERNAL_RESEARCH)
    forbid_facts(monkeypatch)
    external = AsyncMock(return_value=ExternalResearchResult(query="trình tự", provider="test"))
    answer = AsyncMock(return_value="Nguồn công khai đã đối chiếu.")
    monkeypatch.setattr("src.agents.case_graph.answer_external_research", answer)
    result = await build_case_graph(AsyncMock(), external_research=external, standalone=True).ainvoke(
        {
            "latest_user_message": "Tra cứu nguồn công khai",
            "description": "Trao đổi trước đó",
        }
    )
    external.assert_awaited_once()
    answer.assert_awaited_once()
    assert result["question"] == answer.return_value


@pytest.mark.asyncio
async def test_general_and_help_branches_remain_available(monkeypatch):
    routed(monkeypatch, Route.GENERAL_CHAT)
    chat = AsyncMock(return_value=ChatReply("Chào bạn!", "allow"))
    monkeypatch.setattr("src.agents.case_graph.answer_general_chat", chat)
    graph = build_case_graph(AsyncMock(), standalone=True)
    result = await graph.ainvoke({"latest_user_message": "Chào bạn"})
    assert result["question"] == "Chào bạn!"
    routed(monkeypatch, Route.SYSTEM_HELP, help_topic_ids=[HelpTopic.CAPABILITIES])
    result = await graph.ainvoke({"latest_user_message": "Bạn hỗ trợ gì?"})
    assert "chat độc lập" in result["question"] and "mở hồ sơ riêng" in result["question"]


@pytest.mark.asyncio
async def test_router_failure_preserves_safe_boundary(monkeypatch):
    forbidden = forbid_facts(monkeypatch)
    fallback = IntentDecision(
        route=Route.WORKFLOW_ACTION, requested_action="draft_minutes", intent_label="bad", confidence=1
    )
    monkeypatch.setattr(
        "src.agents.case_graph.route_turn",
        AsyncMock(return_value=IntentResult(fallback, IntentFallback.TECHNICAL, "offline", 1, "test")),
    )
    result = await build_case_graph(AsyncMock(), standalone=True).ainvoke({"latest_user_message": "Lập biên bản"})
    assert result["selected_route"] == Route.CLARIFY
    assert "lỗi xử lý" in result["question"]
    forbidden.assert_not_awaited()


def test_scope_is_present_in_router_context():
    assert "CHAT SCOPE: standalone" in render_intent_prompt({"chat_scope": "standalone"})
    assert "CHAT SCOPE: standalone" not in render_intent_prompt({})


@pytest.mark.parametrize("content", ["", "   ", "x" * 8001])
def test_empty_and_oversized_messages_are_rejected(content):
    with pytest.raises(ValidationError):
        StandaloneMessageRequest(content=content)


@pytest.mark.asyncio
async def test_standalone_api_requires_login(client):
    assert (await client.get("/api/v1/conversations")).status_code == 401
    assert (await client.get(f"/api/v1/conversations/{uuid4()}/messages")).status_code == 401
    assert (await client.post("/api/v1/conversations/messages", json={"content": "Xin chào"})).status_code == 401
