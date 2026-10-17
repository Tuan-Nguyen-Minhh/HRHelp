"""Approved Q&A is phrased with conversation memory, without changing graph behavior."""

import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.agents.case_graph import build_case_graph
from src.core.config import settings
from src.features.clarify.model import help_reply, memory
from src.features.clarify.model.assess import StoredFact
from src.features.clarify.model.intent import IntentDecision, IntentFallback, IntentResult, Route
from src.features.clarify.model.system_help import NO_HELP_ANSWER, HelpTopic, answer_system_help


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "SYSTEM_HELP_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")


def generator(monkeypatch, **kwargs):
    invoke = AsyncMock(**kwargs)
    model = Mock()
    model.with_structured_output.return_value.ainvoke = invoke
    factory = Mock(return_value=model)
    monkeypatch.setattr(help_reply, "create_chat_model", factory)
    return invoke, factory


@pytest.mark.asyncio
async def test_formatter_gets_prompt_question_approved_answer_and_scoped_memories(monkeypatch):
    question = "Tôi đã tạo hồ sơ rồi, tiếp theo làm gì?"
    answer = answer_system_help(question, [HelpTopic.MINUTES_START])
    state = {
        "turn_context": "SHORT_TERM_MEMORY\nNgười dùng đã mở hồ sơ; đang chuẩn bị biên bản.",
        "social_context": {
            "help_messages": [
                {"role": "USER", "content": "Mở hồ sơ ở đâu?"},
                {"role": "ASSISTANT", "content": "Chọn Tạo hồ sơ."},
            ],
            "general_messages": [{"role": "USER", "content": "Unrelated casual history"}],
            "routing_clarification": {
                "original_question": "Tôi muốn lập biên bản",
                "question": "Bạn cần hướng dẫn hay lập ngay?",
                "origin_message_id": "internal-id",
            },
        },
        "actor_id": uuid4(),
        "pending_action": "draft_minutes",
        "internal_secret": "must-not-be-sent",
    }
    before = deepcopy(state)
    invoke, factory = generator(monkeypatch, return_value={"answer": "  Mở Hội thoại trong hồ sơ để tiếp tục.  "})
    result = await help_reply.format_help_reply(question, answer, state, chat_scope="standalone")
    assert result == "Mở Hội thoại trong hồ sơ để tiếp tục."
    messages = invoke.call_args.args[0]
    assert messages[0] == {"role": "system", "content": help_reply.SYSTEM_PROMPT}
    payload = json.loads(messages[1]["content"])
    assert payload["question"] == question and payload["qa_answer"] == answer
    assert payload["context_memories"]["turn_context"] == state["turn_context"]
    assert payload["context_memories"]["help_messages"] == state["social_context"]["help_messages"]
    assert payload["context_memories"]["routing_clarification"]["question"] == "Bạn cần hướng dẫn hay lập ngay?"
    assert payload["chat_scope"] == "standalone"
    assert "must-not-be-sent" not in str(messages) and "internal-id" not in str(messages)
    assert "Unrelated casual history" not in str(messages)
    assert state == before
    factory.return_value.bind_tools.assert_not_called()
    invoke.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [RuntimeError("offline"), {"answer": "   "}, {}, {"answer": "x" * 6001}])
async def test_failure_or_invalid_output_keeps_original_answer(monkeypatch, failure):
    kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
    generator(monkeypatch, **kwargs)
    assert await help_reply.format_help_reply("Hỏi", "Đáp án Q&A gốc", {}) == "Đáp án Q&A gốc"


@pytest.mark.asyncio
async def test_slow_formatter_is_cancelled_and_returns_original_answer(monkeypatch):
    cancelled = []

    async def slow(*args):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    monkeypatch.setattr(settings, "SYSTEM_HELP_FORMAT_TIMEOUT_SECONDS", 0.01)
    generator(monkeypatch, side_effect=slow)
    assert await help_reply.format_help_reply("Hỏi", "Đáp án gốc", {}) == "Đáp án gốc"
    assert cancelled == [True]


@pytest.mark.asyncio
async def test_missing_credential_uses_original_answer_without_model_call(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    _, factory = generator(monkeypatch)
    assert await help_reply.format_help_reply("Hỏi", "Đáp án gốc", {}) == "Đáp án gốc"
    factory.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("standalone", [False, True])
@pytest.mark.parametrize(
    "enabled,topics", [(True, []), (True, [HelpTopic.NO_MATCH]), (False, [HelpTopic.MINUTES_START])]
)
async def test_no_answer_or_disabled_help_skips_formatter(monkeypatch, standalone, enabled, topics):
    monkeypatch.setattr(settings, "SYSTEM_HELP_ENABLED", enabled)
    decision = IntentDecision(route=Route.SYSTEM_HELP, intent_label="help", confidence=0.99, help_topic_ids=topics)
    monkeypatch.setattr(
        "src.agents.case_graph.route_turn",
        AsyncMock(return_value=IntentResult(decision, IntentFallback.NONE, None, 1, "test")),
    )
    formatter = AsyncMock(side_effect=AssertionError("No approved answer to format"))
    monkeypatch.setattr("src.agents.case_graph.format_help_reply", formatter)
    result = await build_case_graph(AsyncMock(), standalone=standalone).ainvoke(
        {"latest_user_message": "Câu hỏi", "semantic": True}
    )
    expected = NO_HELP_ANSWER if enabled else "Chức năng hỏi đáp về hệ thống hiện đang tạm tắt."
    assert result["question"] == expected
    formatter.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("standalone", [False, True])
async def test_successful_qa_runs_formatter_inside_existing_node_and_preserves_state(monkeypatch, standalone):
    decision = IntentDecision(
        route=Route.SYSTEM_HELP, intent_label="help", confidence=0.99, help_topic_ids=[HelpTopic.MINUTES_INPUTS]
    )
    monkeypatch.setattr(
        "src.agents.case_graph.route_turn",
        AsyncMock(return_value=IntentResult(decision, IntentFallback.NONE, None, 1, "test")),
    )
    invoke, _ = generator(
        monkeypatch, return_value={"answer": "Bạn đã có hồ sơ; hãy bổ sung diễn biến và tài liệu nếu có."}
    )
    forbidden = AsyncMock(side_effect=AssertionError("Q&A must not run business tools"))
    monkeypatch.setattr("src.agents.case_graph.extract_node", forbidden)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", forbidden)
    stored = {"site_location": StoredFact("Kho A", True)}
    result = await build_case_graph(forbidden, standalone=standalone).ainvoke(
        {
            "latest_user_message": "Cần chuẩn bị gì?",
            "turn_context": "SHORT_TERM_MEMORY\nĐã mở hồ sơ",
            "semantic": True,
            "stored": stored,
            "pending_action": "draft_minutes",
        }
    )
    assert result["question"] == "Bạn đã có hồ sơ; hãy bổ sung diễn biến và tài liệu nếu có."
    payload = json.loads(invoke.call_args.args[0][1]["content"])
    assert "mã nhân viên" in payload["qa_answer"]
    assert payload["context_memories"]["turn_context"].endswith("Đã mở hồ sơ")
    assert payload["chat_scope"] == ("standalone" if standalone else "case")
    assert result["selected_route"] == Route.SYSTEM_HELP
    assert result["merged"] == stored and result["pending_action"] == "draft_minutes"
    assert result["state_update"] == "preserve" and result["task_change"] == "keep"
    assert result["requested_action"] == "" and not result.get("handoff")
    invoke.assert_awaited_once()
    forbidden.assert_not_awaited()


@pytest.mark.asyncio
async def test_help_history_excludes_other_scopes_internal_messages_and_respects_window(monkeypatch):
    rows = [
        SimpleNamespace(role=role, content=f"help-{index}-{role}", message_metadata={"context_scope": "system_help"})
        for index in range(6)
        for role in ("USER", "ASSISTANT")
    ]
    rows.extend(
        [
            SimpleNamespace(role="ASSISTANT", content="legacy help", message_metadata={"kind": "system_help"}),
            SimpleNamespace(
                role="ASSISTANT", content="secret", message_metadata={"context_scope": "system_help", "internal": True}
            ),
            SimpleNamespace(role="USER", content="business", message_metadata={}),
            SimpleNamespace(
                role="USER",
                content="casual",
                message_metadata={"context_scope": "general", "include_in_general_context": True},
            ),
        ]
    )
    monkeypatch.setattr(memory, "list_messages", AsyncMock(return_value=rows))
    result = await memory.side_context(AsyncMock(), uuid4())
    assert len(result["help_messages"]) == 8
    assert result["help_messages"][0]["content"] == "help-2-ASSISTANT"
    assert result["help_messages"][-1]["content"] == "legacy help"
    assert all(item["content"] not in {"secret", "business", "casual"} for item in result["help_messages"])
    assert result["general_messages"] == [{"role": "USER", "content": "casual"}]
