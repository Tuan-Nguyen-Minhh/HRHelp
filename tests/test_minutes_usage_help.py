"""Approved usage Q&A answers the reported question without executing a case workflow."""

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.agents.case_graph import build_case_graph
from src.agents.conversation import TaskChange
from src.core.config import settings
from src.features.clarify.model import intent
from src.features.clarify.model.assess import StoredFact
from src.features.clarify.model.intent import IntentDecision, IntentFallback, IntentResult, RecheckDecision, Route
from src.features.clarify.model.system_help import HelpTopic, answer_system_help

pytestmark = pytest.mark.usefixtures("approved_help_reply")


@pytest.mark.asyncio
@pytest.mark.parametrize("standalone", [False, True])
@pytest.mark.parametrize(
    "question",
    [
        "tôi muốn lập biên bản thì phải làm như nào",
        "TÔI MUỐN LẬP BIÊN BẢN THÌ PHẢI LÀM NHƯ THẾ NÀO?",
        "toi muon lap bien ban thi phai lam nhu nao?",
        "Tôi cần vào đâu để lập biên bản?",
    ],
)
async def test_usage_answer_preserves_state_after_normal_semantic_classification(monkeypatch, standalone, question):
    monkeypatch.setattr(settings, "SYSTEM_HELP_ENABLED", True)
    chosen = IntentDecision(
        route=Route.SYSTEM_HELP, intent_label="usage", confidence=0.99, help_topic_ids=[HelpTopic.MINUTES_START]
    )
    classify = AsyncMock(return_value=IntentResult(chosen, IntentFallback.NONE, None, 1, "test"))
    extract = AsyncMock(side_effect=AssertionError("A usage question cannot collect facts"))
    retrieve = AsyncMock(side_effect=AssertionError("A usage question cannot retrieve case policies"))
    monkeypatch.setattr(intent, "_classify_turn", classify)
    monkeypatch.setattr("src.agents.case_graph.extract_node", extract)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", extract)
    stored = {"site_location": StoredFact("Kho A", True)}
    result = await build_case_graph(retrieve, standalone=standalone).ainvoke(
        {
            "latest_user_message": question,
            "semantic": True,
            "stored": stored,
            "pending_action": "draft_minutes",
        }
    )
    assert result["selected_route"] == Route.SYSTEM_HELP
    assert result["help_topic_ids"] == [HelpTopic.MINUTES_START]
    assert "1. Bấm Tạo hồ sơ" in result["question"]
    assert "Tình tiết vi phạm" in result["question"]
    assert "Đánh giá và biên bản" in result["question"]
    assert "Xuất Word" in result["question"]
    assert result["merged"] == stored
    assert result["pending_action"] == "draft_minutes"
    assert result["task_change"] == TaskChange.KEEP.value
    assert result["state_update"] == "preserve"
    assert result["requested_action"] == ""
    assert not result.get("handoff")
    classify.assert_awaited_once()
    extract.assert_not_awaited()
    retrieve.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "tôi muốn lập biên bản thì phải làm như nào",
        "tôi muốn lập biên bản thì phải cung cấp những thông tin gì",
        "Hãy lập biên bản vụ này cho tôi",
        "Lập biên bản cần những bước nào theo luật?",
        "Đã lập biên bản",
        "Biên bản đang lưu có gì?",
        "Tôi muốn lập biên bản thì phải làm như nào; hãy lập ngay cho tôi",
    ],
)
async def test_every_question_uses_existing_semantic_router_without_catalog_shortcut(monkeypatch, question):
    expected = object()
    classify = AsyncMock(return_value=expected)
    monkeypatch.setattr(intent, "_classify_turn", classify)
    state = {"latest_user_message": question}
    assert await intent.route_turn(state) is expected
    classify.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_usage_paraphrase_is_semantically_rechecked_instead_of_workflow_keyword_override(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")
    question = "Chỉ giúp tôi các nút cần bấm để lập biên bản trên phần mềm"
    initial = IntentDecision(
        route=Route.WORKFLOW_ACTION, requested_action="draft_minutes", intent_label="initial", confidence=0.9
    )
    confirmed = IntentDecision(
        route=Route.SYSTEM_HELP, help_topic_ids=[HelpTopic.MINUTES_START], intent_label="ask_usage", confidence=0.99
    )
    complete = AsyncMock(return_value=initial)
    recheck = AsyncMock(return_value=RecheckDecision(status="confirmed", decision=confirmed))
    monkeypatch.setattr(intent, "_complete", complete)
    monkeypatch.setattr(intent, "_recheck", recheck)
    result = await intent.route_turn({"latest_user_message": question})
    assert result.decision.route == Route.SYSTEM_HELP
    assert result.decision.help_topic_ids == [HelpTopic.MINUTES_START]
    assert result.decision.requested_action == ""
    assert result.rule_matches
    recheck.assert_awaited_once()


def test_usage_topic_returns_navigation_answer(monkeypatch):
    monkeypatch.setattr(settings, "SYSTEM_HELP_ENABLED", True)
    answer = answer_system_help("tôi muốn lập biên bản thì phải làm như nào?", [HelpTopic.MINUTES_START])
    assert "1. Bấm Tạo hồ sơ" in answer
    assert "chưa tạo hay gửi biên bản" in answer


def test_usage_qa_respects_feature_switch(monkeypatch):
    monkeypatch.setattr(settings, "SYSTEM_HELP_ENABLED", False)
    assert "tạm tắt" in answer_system_help("tôi muốn lập biên bản thì phải làm như nào", [HelpTopic.MINUTES_START])


@pytest.mark.asyncio
@pytest.mark.parametrize("standalone", [False, True])
async def test_information_question_answers_preparation_without_starting_fact_collection(monkeypatch, standalone):
    monkeypatch.setattr(settings, "SYSTEM_HELP_ENABLED", True)
    chosen = IntentDecision(
        route=Route.SYSTEM_HELP,
        intent_label="ask_required_information",
        confidence=0.98,
        help_topic_ids=[HelpTopic.MINUTES_INPUTS],
    )
    classify = AsyncMock(return_value=IntentResult(chosen, IntentFallback.NONE, None, 1, "test"))
    monkeypatch.setattr(intent, "_classify_turn", classify)
    forbidden = AsyncMock(side_effect=AssertionError("Explaining preparation cannot collect facts or retrieve"))
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", forbidden)
    result = await build_case_graph(forbidden, standalone=standalone).ainvoke(
        {
            "latest_user_message": "tôi muốn lập biên bản thì phải cung cấp những thông tin gì",
            "semantic": True,
            "pending_action": "draft_minutes",
        }
    )
    assert result["selected_route"] == Route.SYSTEM_HELP
    assert result["help_topic_ids"] == [HelpTopic.MINUTES_INPUTS]
    assert "mã nhân viên" in result["question"] and "diễn biến" in result["question"]
    assert "Tài liệu liên quan nếu có" in result["question"]
    assert "1. Bấm Tạo hồ sơ" not in result["question"]
    assert result["pending_action"] == "draft_minutes" and result["state_update"] == "preserve"
    classify.assert_awaited_once()
    forbidden.assert_not_awaited()


NO_ANSWER = "Tôi tạm thời chưa thể trả lời cho bạn, bạn có thể hỏi kỹ hơn hoặc hỏi câu khác."


@pytest.mark.asyncio
@pytest.mark.parametrize("standalone", [False, True])
async def test_help_without_matching_answer_returns_requested_fallback_verbatim(monkeypatch, standalone):
    monkeypatch.setattr(settings, "SYSTEM_HELP_ENABLED", True)
    chosen = IntentDecision(route=Route.SYSTEM_HELP, intent_label="ask_unknown_product_usage", confidence=0.99)
    monkeypatch.setattr(
        "src.agents.case_graph.route_turn",
        AsyncMock(return_value=IntentResult(chosen, IntentFallback.NONE, None, 1, "test")),
    )
    retrieve = AsyncMock(side_effect=AssertionError("Missing Q&A must not fall through to RAG"))
    result = await build_case_graph(retrieve, standalone=standalone).ainvoke(
        {
            "latest_user_message": "Tùy chỉnh phê duyệt song song trong cấu hình ở đâu?",
            "semantic": True,
        }
    )
    assert result["question"] == NO_ANSWER
    assert result["selected_route"] == Route.SYSTEM_HELP
    retrieve.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("standalone", [False, True])
async def test_explicit_no_match_topic_does_not_redirect_to_another_branch(monkeypatch, standalone):
    monkeypatch.setattr(settings, "SYSTEM_HELP_ENABLED", True)
    chosen = IntentDecision(
        route=Route.SYSTEM_HELP, help_topic_ids=[HelpTopic.NO_MATCH], intent_label="unknown_usage", confidence=0.95
    )
    monkeypatch.setattr(
        "src.agents.case_graph.route_turn",
        AsyncMock(return_value=IntentResult(chosen, IntentFallback.NONE, None, 1, "test")),
    )
    forbidden = AsyncMock(side_effect=AssertionError("Unknown Q&A has no retrieval or fact tools"))
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", forbidden)
    result = await build_case_graph(forbidden, standalone=standalone).ainvoke(
        {
            "semantic": True,
            "latest_user_message": "Cài đặt nhánh phê duyệt song song ở đâu?",
            "pending_action": "draft_minutes",
        }
    )
    assert result["question"] == NO_ANSWER
    assert result["help_topic_ids"] == [HelpTopic.NO_MATCH]
    assert result["state_update"] == "preserve" and result["pending_action"] == "draft_minutes"
    forbidden.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_route", [Route.POLICY_QA, Route.WORKFLOW_ACTION])
@pytest.mark.parametrize(
    "question",
    [
        "Quy trình lập biên bản như thế nào?",
        "Cách thức lập biên bản ra sao?",
        "Lập biên bản như nào?",
    ],
)
async def test_procedure_paraphrases_are_rechecked_against_qa_card(monkeypatch, initial_route, question):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")
    action = "draft_minutes" if initial_route == Route.WORKFLOW_ACTION else "answer_policy_question"
    initial = IntentDecision(route=initial_route, requested_action=action, intent_label="initial", confidence=0.9)
    corrected = IntentDecision(
        route=Route.SYSTEM_HELP, help_topic_ids=[HelpTopic.MINUTES_START], intent_label="usage", confidence=0.98
    )
    monkeypatch.setattr(intent, "_complete", AsyncMock(return_value=initial))
    recheck = AsyncMock(return_value=RecheckDecision(status="confirmed", decision=corrected))
    monkeypatch.setattr(intent, "_recheck", recheck)
    result = await intent.route_turn({"latest_user_message": question})
    assert result.decision.route == Route.SYSTEM_HELP
    assert result.rule_matches
    prompt = recheck.call_args.args[0][0]["content"]
    assert "Q&A TOPICS" in prompt
    assert "minutes_required_information" in prompt
    assert "no_matching_answer" in prompt


def test_unknown_direct_qa_returns_requested_fallback(monkeypatch):
    monkeypatch.setattr(settings, "SYSTEM_HELP_ENABLED", True)
    assert answer_system_help("Một chức năng chưa có trong Q&A", []) == NO_ANSWER


def test_long_diagnostic_reason_does_not_reject_valid_no_answer_decision():
    decision = {
        "route": "system_help",
        "intent_label": "unknown_usage",
        "confidence": 0.98,
        "help_topic_ids": ["no_matching_answer"],
        "reason": "Giải thích chẩn đoán dài. " * 30,
    }
    parsed = RecheckDecision.model_validate({"status": "confirmed", "decision": decision})
    assert parsed.decision.route == Route.SYSTEM_HELP
    assert parsed.decision.help_topic_ids == [HelpTopic.NO_MATCH]
    assert len(parsed.decision.reason) == 300
    with pytest.raises(ValidationError):
        RecheckDecision.model_validate(
            {"status": "confirmed", "decision": {**decision, "requested_action": "draft_minutes"}}
        )
