"""Semantic recheck and side branches: no lexical override or business side effects."""

from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError

from src.agents.case_graph import _decide_intent_route, build_case_graph
from src.agents.conversation import memory_patch
from src.core.config import settings
from src.features.clarify.model import intent
from src.features.clarify.model.assess import ClarifyPlan, StoredFact
from src.features.clarify.model.catalog import FactSpec
from src.features.clarify.model.general_chat import ChatReply
from src.features.clarify.model.intent import IntentDecision, IntentFallback, IntentResult, RecheckDecision, Route
from src.features.clarify.model.route_rules import detect_route_hypotheses
from src.features.clarify.model.system_help import HelpTopic, answer_system_help

pytestmark = pytest.mark.usefixtures("approved_help_reply")


def decision(route=Route.CASE_QA, **kwargs):
    return IntentDecision(route=route, intent_label="test_intent", confidence=0.95, **kwargs)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key-not-a-secret")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        "Hồ sơ này đang chờ phê duyệt ở đâu?",
        "Hồ sơ này hiện nay đang ở bước nào?",
        "Hồ sơ này có mức kỷ luật đang lưu là gì?",
    ],
)
async def test_keyword_hits_recheck_without_overwriting_correct_case_read(configured, monkeypatch, message):
    initial = decision()
    first = AsyncMock(return_value=initial)
    recheck = AsyncMock(return_value=RecheckDecision(status="confirmed", decision=initial))
    monkeypatch.setattr(intent, "_complete", first)
    monkeypatch.setattr(intent, "_recheck", recheck)
    result = await intent.route_turn({"latest_user_message": message})
    first.assert_awaited_once()
    recheck.assert_awaited_once()
    assert result.rule_matches
    assert result.initial_decision == initial.model_dump(mode="json")
    assert result.decision == initial
    assert result.recheck_status == "confirmed"
    assert not result.decision.signals.asks_prohibited_action
    assert _decide_intent_route({}, result.decision, result.fallback_kind)[0] == Route.CASE_QA


@pytest.mark.asyncio
async def test_same_route_hit_still_rechecks_and_multiple_hits_share_one_pass(configured, monkeypatch):
    first = decision(Route.UNSUPPORTED, requested_action="unsupported")
    check = AsyncMock(return_value=RecheckDecision(status="confirmed", decision=first))
    monkeypatch.setattr(intent, "_complete", AsyncMock(return_value=first))
    monkeypatch.setattr(intent, "_recheck", check)
    result = await intent.route_turn({"latest_user_message": "Phê duyệt hồ sơ này theo luật hiện nay"})
    assert len(result.rule_matches) >= 3
    assert result.decision.route == Route.UNSUPPORTED
    check.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("chosen", [Route.UNSUPPORTED, Route.SYSTEM_HELP, Route.GENERAL_CHAT])
async def test_recheck_can_choose_rule_candidate_or_third_route(configured, monkeypatch, chosen):
    final = decision(chosen)
    monkeypatch.setattr(intent, "_complete", AsyncMock(return_value=decision()))
    monkeypatch.setattr(intent, "_recheck", AsyncMock(return_value=RecheckDecision(status="confirmed", decision=final)))
    result = await intent.route_turn({"latest_user_message": "Bạn xử lý phê duyệt giúp tôi"})
    assert result.decision.route == chosen


@pytest.mark.asyncio
async def test_no_hit_keeps_valid_semantics_without_extra_model_call(configured, monkeypatch):
    first = decision()
    check = AsyncMock(side_effect=AssertionError("No recheck needed"))
    monkeypatch.setattr(intent, "_complete", AsyncMock(return_value=first))
    monkeypatch.setattr(intent, "_recheck", check)
    result = await intent.route_turn({"latest_user_message": "Tóm tắt sự việc"})
    assert result.decision == first
    check.assert_not_awaited()


@pytest.mark.asyncio
async def test_contract_conflict_rechecks_even_without_keyword_hit(configured, monkeypatch):
    bad = decision(Route.GENERAL_CHAT, requested_action="send_to_legal")
    check = AsyncMock(return_value=RecheckDecision(status="confirmed", decision=decision(Route.GENERAL_CHAT)))
    monkeypatch.setattr(intent, "_complete", AsyncMock(return_value=bad))
    monkeypatch.setattr(intent, "_recheck", check)
    result = await intent.route_turn({"latest_user_message": "Đổi gió nào"})
    assert result.decision.requested_action == ""
    assert "action_not_allowed_for_route" in check.call_args.args[3]


@pytest.mark.asyncio
async def test_ambiguous_recheck_asks_specific_question_and_cannot_run_action(configured, monkeypatch):
    question = "Bạn muốn hướng dẫn bước duyệt hay yêu cầu thực hiện phê duyệt?"
    monkeypatch.setattr(intent, "_complete", AsyncMock(return_value=decision(Route.SYSTEM_HELP)))
    monkeypatch.setattr(
        intent,
        "_recheck",
        AsyncMock(return_value=RecheckDecision(status="needs_clarification", clarification_question=question)),
    )
    planner = AsyncMock(side_effect=AssertionError("No facts may be extracted"))
    retrieve = AsyncMock(side_effect=AssertionError("No retrieval allowed"))
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", planner)
    state = await build_case_graph(retrieve).ainvoke(
        {
            "semantic": True,
            "latest_user_message": "Bạn xử lý phê duyệt giúp tôi",
            "pending_action": "draft_minutes",
            "pending_fact_keys": ["site_location"],
            "active_specs": [FactSpec("site_location", "Địa điểm", "Ở đâu?")],
            "stored": {"known": StoredFact("giữ lại", True)},
        }
    )
    assert state["selected_route"] == Route.CLARIFY
    assert state["question"] == question
    assert state["state_update"] == "preserve"
    assert state["task_change"] == "keep"
    assert state["merged"]["known"].value == "giữ lại"
    planner.assert_not_awaited()
    retrieve.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("exc", [ValueError("invalid recheck"), httpx.ConnectError("offline")])
async def test_recheck_failure_does_not_accept_initial_guess_or_run_fact_planner(configured, monkeypatch, exc):
    first = AsyncMock(return_value=decision(Route.WORKFLOW_ACTION, requested_action="draft_minutes"))
    check = AsyncMock(side_effect=exc)
    monkeypatch.setattr(intent, "_complete", first)
    monkeypatch.setattr(intent, "_recheck", check)
    result = await intent.route_turn({"latest_user_message": "Lập biên bản"})
    assert result.decision.route == Route.CLARIFY
    assert result.fallback
    assert result.recheck_status == "failed"
    assert _decide_intent_route({}, result.decision, result.fallback_kind)[0] == Route.CLARIFY
    first.assert_awaited_once()
    check.assert_awaited_once()


def test_recheck_schema_rejects_contradictory_confirmations():
    with pytest.raises(ValidationError):
        RecheckDecision(status="confirmed")
    with pytest.raises(ValidationError):
        RecheckDecision(status="needs_clarification")
    with pytest.raises(ValidationError):
        RecheckDecision(status="confirmed", decision=decision(Route.SYSTEM_HELP, requested_action="send_to_legal"))


@pytest.mark.asyncio
@pytest.mark.parametrize("route", [Route.GENERAL_CHAT, Route.SYSTEM_HELP])
async def test_new_graph_branches_keep_locked_facts_and_pending_task(monkeypatch, route):
    resolved = decision(route, help_topic_ids=[HelpTopic.AUTHORITY] if route == Route.SYSTEM_HELP else [])
    monkeypatch.setattr(
        "src.agents.case_graph.route_turn",
        AsyncMock(return_value=IntentResult(resolved, IntentFallback.NONE, None, 1, "test")),
    )
    monkeypatch.setattr(
        "src.agents.case_graph.answer_general_chat", AsyncMock(return_value=ChatReply("Chào bạn!", "allow"))
    )
    planner = AsyncMock(side_effect=AssertionError("Side branch must not collect facts"))
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", planner)
    search = AsyncMock(side_effect=AssertionError("Side branch must not retrieve"))
    external = AsyncMock(side_effect=AssertionError("Side branch must not search web"))
    specs = [FactSpec("site_location", "Địa điểm", "Ở đâu?")]
    stored = {"site_location": StoredFact("Kho A", True)}
    state = await build_case_graph(search, external_research=external).ainvoke(
        {
            "semantic": True,
            "latest_user_message": "Một câu hỏi bên lề",
            "stored": stored,
            "active_specs": specs,
            "pending_action": "draft_minutes",
            "pending_fact_keys": [],
        }
    )
    assert state["reply_kind"] == route.value
    assert state["facts_locked"] is True
    assert state["merged"] == stored and state["accepted_keys"] == []
    assert state["task_change"] == "keep" and state["state_update"] == "preserve"
    assert state["requested_action"] == "" and state.get("handoff") is None
    assert memory_patch(ClarifyPlan("GENERAL", stored, [], True, specs=tuple(specs), state_update="preserve")) == {}
    planner.assert_not_awaited()
    search.assert_not_awaited()
    external.assert_not_awaited()


@pytest.mark.asyncio
async def test_clarification_reply_receives_original_question_without_replacing_workflow(configured, monkeypatch):
    state = {
        "latest_user_message": "Tôi chỉ hỏi quyền của AI",
        "pending_action": "draft_minutes",
        "social_context": {
            "routing_clarification": {
                "original_question": "Bạn xử lý duyệt giúp tôi",
                "question": "Hỏi quyền hay yêu cầu duyệt?",
            }
        },
    }
    first = AsyncMock(return_value=decision(Route.SYSTEM_HELP, help_topic_ids=[HelpTopic.AUTHORITY]))
    monkeypatch.setattr(intent, "_complete", first)
    result = await intent.route_turn(state)
    prompt = first.call_args.args[0]
    assert "Bạn xử lý duyệt giúp tôi" in prompt[1]["content"]
    assert "Tôi chỉ hỏi quyền của AI" in prompt[1]["content"]
    assert result.decision.task_change.value == "keep"


@pytest.mark.parametrize("text", ["phe duyet", "PHÊ DUYỆT", "phê duyệt", "Phê   duyệt"])
def test_rules_accept_vietnamese_variants_without_changing_decision(text):
    assert any(hit["candidate_route"] == "unsupported" for hit in detect_route_hypotheses(text))


def test_help_answers_approved_topics_without_generation(monkeypatch):
    monkeypatch.setattr(settings, "SYSTEM_HELP_ENABLED", True)
    for topic in HelpTopic:
        assert answer_system_help("Một cách hỏi khác", [topic])
    assert "không quyết định thay" in answer_system_help("AI có quyền phê duyệt không?")
    monkeypatch.setattr(settings, "EXTERNAL_RESEARCH_ENABLED", False)
    assert "chưa được bật" in answer_system_help("Tra cứu nguồn nào?", [HelpTopic.SOURCES])
    monkeypatch.setattr(settings, "EXTERNAL_RESEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "EXTERNAL_RESEARCH_PROVIDER", "brave")
    monkeypatch.setattr(settings, "BRAVE_SEARCH_API_KEY", "test")
    assert "đang được bật" in answer_system_help("Tra cứu nguồn nào?", [HelpTopic.SOURCES])


@pytest.mark.asyncio
async def test_total_router_timeout_preserves_without_extracting(monkeypatch):
    import asyncio

    async def delayed(_state):
        await asyncio.sleep(5)

    monkeypatch.setattr(intent, "_classify_turn", delayed)
    monkeypatch.setattr(settings, "INTENT_TOTAL_TIMEOUT_SECONDS", 0.01)
    result = await intent.route_turn({"latest_user_message": "Phê duyệt"})
    assert result.fallback_kind == IntentFallback.TECHNICAL
    assert result.decision.route == Route.CLARIFY and result.reason == "routing_timeout"


def test_repeated_clarification_retains_original_request():
    from src.features.clarify.model.turns import _with_reply_metadata

    previous = {"original_question": "Bạn xử lý phần duyệt giúp tôi", "origin_message_id": "original-id"}
    plan = ClarifyPlan("GENERAL", {}, [], False, question="Hỏi quyền hay yêu cầu thực hiện?", state_update="preserve")
    state = {"reply_kind": "clarify", "social_context": {"routing_clarification": previous}}
    result = _with_reply_metadata(plan, state, "Ý tôi là phần đó")
    assert result.reply_metadata["routing_clarification"]["original_question"] == previous["original_question"]
    assert result.reply_metadata["routing_clarification"]["origin_message_id"] == "original-id"
    assert result.reply_metadata["routing_clarification"]["latest_reply"] == "Ý tôi là phần đó"
    failed = _with_reply_metadata(plan, {**state, "intent_router_fallback": True}, "Thử lại")
    assert failed.reply_kind == "routing_error"
    assert failed.reply_metadata["routing_clarification"] == previous


def test_business_handlers_and_planner_receive_clarified_question_not_casual_history():
    from src.agents.case_graph import _resolved_question
    from src.features.clarify.model.planner import _messages

    state = {
        "latest_user_message": "Tôi muốn xem nội dung đã lưu",
        "social_context": {
            "routing_clarification": {
                "original_question": "Biên bản này thế nào?",
                "question": "Xem nội dung hay hỏi quy định?",
            },
            "general_messages": [{"role": "USER", "content": "CHUYỆN ĂN TRƯA"}],
        },
    }
    resolved = _resolved_question(state)
    assert "Biên bản này thế nào?" in resolved and "Tôi muốn xem nội dung đã lưu" in resolved
    prompt = _messages(state)[1]["content"]
    assert "Biên bản này thế nào?" in prompt and "ROUTING_CLARIFICATION" in prompt
    assert "CHUYỆN ĂN TRƯA" not in prompt
