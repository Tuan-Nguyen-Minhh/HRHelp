"""Semantic context is source-linked, refreshed per turn and separate from case state."""

import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.agents.case_graph import _resolved_question, build_case_graph
from src.core.config import settings
from src.features.clarify.model import dialogue_context as dc
from src.features.clarify.model import help_reply, intent, planner
from src.features.clarify.model.assess import StoredFact
from src.features.clarify.model.intent import IntentDecision, IntentFallback, IntentResult, Route
from src.features.clarify.model.system_help import HelpTopic


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")


def row(cid, mid, role, content, **metadata):
    return SimpleNamespace(conversation_id=cid, id=mid, role=role, content=content, message_metadata=metadata)


def history(cid):
    return [
        row(cid, "u1", "USER", "Muốn lập biên bản thì bắt đầu ở đâu?", context_scope="system_help"),
        row(
            cid, "a1", "ASSISTANT", "Bấm Tạo hồ sơ, mở Hội thoại rồi yêu cầu lập biên bản.", context_scope="system_help"
        ),
        row(cid, "u2", "USER", "Vậy cần chuẩn bị những thông tin gì?"),
    ]


def interpretation(latest="u2", text="Tôi cần chuẩn bị những thông tin gì để lập biên bản?", previous="a1"):
    note = {"text": text, "source_ids": [previous, latest]}
    return {
        "current_goal": note,
        "interpreted_question": note,
        "topic_transition": "follow_up",
        "links": [
            {
                "from_id": latest,
                "to_id": previous,
                "relation": "follow_up",
                "meaning": "Hỏi đầu vào sau khi đã được hướng dẫn nơi bắt đầu.",
            }
        ],
        "context_summary": [
            {
                "text": "Trợ lý đã hướng dẫn mở hồ sơ; user đang hỏi thông tin cần chuẩn bị.",
                "source_ids": [previous, latest],
            }
        ],
        "corrections": [],
        "open_questions": [],
        "uncertainty": "",
    }


def model_stub(monkeypatch, **kwargs):
    invoke = AsyncMock(**kwargs)
    model = Mock()
    model.with_structured_output.return_value.ainvoke = invoke
    factory = Mock(return_value=model)
    monkeypatch.setattr(dc, "create_chat_model", factory)
    return invoke, factory


@pytest.mark.asyncio
async def test_analyzes_ordered_question_answer_links_and_preserves_original_data(monkeypatch):
    cid = uuid4()
    rows = history(cid)
    before = deepcopy(rows)
    invoke, factory = model_stub(monkeypatch, return_value=interpretation())
    result = await dc.build_dialogue_context(AsyncMock(), cid, rows[-1].content, rows=rows, chat_scope="standalone")
    assert result["status"] == "ready"
    assert result["analysis"]["interpreted_question"]["text"].endswith("để lập biên bản?")
    assert result["analysis"]["links"][0]["to_id"] == "a1"
    assert result["through_message_id"] == "u2" and result["source_ids"] == ["a1", "u2"]
    payload = json.loads(invoke.call_args.args[0][1]["content"])
    assert [turn["id"] for turn in payload["source_turns"]] == ["u1", "a1", "u2"]
    assert [turn["scope"] for turn in payload["source_turns"]] == ["system_help", "system_help", "business"]
    assert payload["latest_user_message"]["content"] == rows[-1].content
    assert payload["previous_context"] is None and not payload["history_gap"]
    assert payload["chat_scope"] == "standalone"
    assert rows == before
    factory.return_value.bind_tools.assert_not_called()
    assert factory.call_args.kwargs["max_retries"] == 0


@pytest.mark.asyncio
async def test_checkpoint_updates_goal_and_corrections_using_fresh_sources(monkeypatch):
    cid = uuid4()
    rows = history(cid)
    second = interpretation("u3", "Tôi cần thông tin cho biên bản sự việc, không phải họp kỷ luật.", "a2")
    second["corrections"] = [{"text": "User làm rõ loại biên bản là sự việc.", "source_ids": ["u2", "u3"]}]
    invoke, _ = model_stub(monkeypatch, side_effect=[interpretation(), second])
    first = await dc.build_dialogue_context(AsyncMock(), cid, rows[-1].content, rows=rows)
    metadata = dc.context_metadata(first)
    assert "source_turns" not in metadata["dialogue_context"]
    rows.extend(
        [
            row(cid, "a2", "ASSISTANT", "Bạn muốn biên bản họp kỷ luật?", **metadata),
            row(cid, "u3", "USER", "Không phải họp kỷ luật, tôi hỏi biên bản sự việc."),
        ]
    )
    result = await dc.build_dialogue_context(AsyncMock(), cid, rows[-1].content, rows=rows)
    payload = json.loads(invoke.call_args_list[1].args[0][1]["content"])
    assert payload["previous_context"] == first["analysis"]
    assert result["through_message_id"] == "u3" and "u3" in result["analysis"]["current_goal"]["source_ids"]
    assert result["analysis"]["corrections"] == second["corrections"]
    assert result["analysis"]["interpreted_question"] != first["analysis"]["interpreted_question"]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["foreign_source", "wrong_latest", "backward_link", "route_injection", "blank"])
async def test_invalid_analysis_falls_back_without_a_checkpoint(monkeypatch, invalid):
    cid = uuid4()
    rows = history(cid)
    response = interpretation()
    if invalid == "foreign_source":
        response["context_summary"][0]["source_ids"] = ["another-conversation-id"]
    elif invalid == "wrong_latest":
        response["current_goal"]["source_ids"] = ["a1"]
    elif invalid == "backward_link":
        response["links"][0].update(from_id="a1", to_id="u2")
    elif invalid == "route_injection":
        response["requested_action"] = "draft_minutes"
    else:
        response["interpreted_question"]["text"] = "  "
    model_stub(monkeypatch, return_value=response)
    result = await dc.build_dialogue_context(AsyncMock(), cid, rows[-1].content, rows=rows)
    assert result == {"status": "unavailable"}
    assert dc.context_metadata(result) == {"dialogue_context_status": "unavailable"}


@pytest.mark.asyncio
async def test_excludes_other_conversations_internal_and_unreleased_general_turns(monkeypatch):
    cid = uuid4()
    rows = history(cid)
    rows[1:1] = [
        row(uuid4(), "foreign", "ASSISTANT", "Foreign confidential case"),
        row(cid, "internal", "ASSISTANT", "Internal secret", internal=True),
        row(cid, "blocked", "USER", "Unsafe casual text", context_scope="general", include_in_general_context=False),
    ]
    invoke, _ = model_stub(monkeypatch, return_value=interpretation())
    assert (await dc.build_dialogue_context(AsyncMock(), cid, rows[-1].content, rows=rows))["status"] == "ready"
    content = invoke.call_args.args[0][1]["content"]
    assert "Foreign confidential" not in content and "Internal secret" not in content and "Unsafe casual" not in content


@pytest.mark.asyncio
async def test_budget_reports_history_gap_and_rehydrates_older_checkpoint_sources(monkeypatch):
    cid = uuid4()
    rows = history(cid)
    invoke, _ = model_stub(monkeypatch, side_effect=[interpretation(), interpretation("u30", previous="a1")])
    first = await dc.build_dialogue_context(AsyncMock(), cid, rows[-1].content, rows=rows)
    rows.append(row(cid, "a2", "ASSISTANT", "Thông tin đầu vào...", **dc.context_metadata(first)))
    for i in range(3, 30):
        rows.extend([row(cid, f"u{i}", "USER", f"Hỏi khác {i}"), row(cid, f"a{i}", "ASSISTANT", f"Trả lời {i}")])
    rows.append(row(cid, "u30", "USER", "Quay lại biên bản lúc đầu, tôi cần chuẩn bị gì?"))
    result = await dc.build_dialogue_context(AsyncMock(), cid, rows[-1].content, rows=rows)
    payload = json.loads(invoke.call_args_list[-1].args[0][1]["content"])
    assert len(payload["source_turns"]) == dc.RECENT_LIMIT
    assert payload["history_gap"] and result["history_gap"]
    assert payload["previous_context"] == first["analysis"]
    assert {turn["id"] for turn in payload["previous_source_turns"]} == {"a1", "u2"}
    assert result["through_message_id"] == "u30"


@pytest.mark.asyncio
async def test_timeout_does_not_reuse_stale_interpretation(monkeypatch):
    cid = uuid4()
    rows = history(cid)
    invoke, _ = model_stub(monkeypatch, return_value=interpretation())
    first = await dc.build_dialogue_context(AsyncMock(), cid, rows[-1].content, rows=rows)
    rows.extend(
        [
            row(cid, "a2", "ASSISTANT", "Trả lời", **dc.context_metadata(first)),
            row(cid, "u3", "USER", "Tôi hỏi một điều khác"),
        ]
    )
    cancelled = []

    async def slow(*args):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    invoke.side_effect = slow
    monkeypatch.setattr(settings, "DIALOGUE_CONTEXT_TIMEOUT_SECONDS", 0.01)
    result = await dc.build_dialogue_context(AsyncMock(), cid, rows[-1].content, rows=rows)
    assert result == {"status": "unavailable"} and cancelled == [True]
    assert "analysis" not in dc.context_for_prompt({"dialogue_context": result})


@pytest.mark.asyncio
async def test_long_current_message_is_kept_whole_including_its_final_correction(monkeypatch):
    cid = uuid4()
    rows = history(cid)
    question = "Thông tin tôi vừa cung cấp. " * 700 + "Nhưng tôi chỉ hỏi hướng dẫn, chưa yêu cầu lập ngay."
    rows[-1].content = question
    response = interpretation()
    response["uncertainty"] = "History was truncated; current user only asks for guidance."
    invoke, _ = model_stub(monkeypatch, return_value=response)
    # This output cites a source outside the supplied window and must be rejected.
    result = await dc.build_dialogue_context(AsyncMock(), cid, question, rows=rows)
    payload = json.loads(invoke.call_args.args[0][1]["content"])
    assert payload["source_turns"][-1]["content"] == question
    assert payload["latest_user_message"]["content"].endswith("chưa yêu cầu lập ngay.")
    assert payload["history_gap"]
    assert result == {"status": "unavailable"}


@pytest.mark.asyncio
@pytest.mark.parametrize("condition", ["no_history", "no_key", "wrong_message", "malformed_checkpoint"])
async def test_cold_start_and_legacy_messages_are_supported(monkeypatch, condition):
    cid = uuid4()
    rows = history(cid)
    invoke, factory = model_stub(monkeypatch, return_value=interpretation())
    question = rows[-1].content
    if condition == "no_history":
        rows = [rows[-1]]
    elif condition == "no_key":
        monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    elif condition == "wrong_message":
        question = "not the saved user question"
    else:
        rows[1].message_metadata["dialogue_context"] = {"version": "old", "through_message_id": "foreign"}
    result = await dc.build_dialogue_context(AsyncMock(), cid, question, rows=rows)
    if condition == "malformed_checkpoint":
        assert result["status"] == "ready"
        assert json.loads(invoke.call_args.args[0][1]["content"])["previous_context"] is None
    else:
        assert result["status"] == ("no_history" if condition == "no_history" else "unavailable")
        factory.assert_not_called()


@pytest.mark.asyncio
async def test_existing_consumers_receive_interpretation_but_do_not_promote_it_to_facts(monkeypatch):
    cid = uuid4()
    rows = history(cid)
    model_stub(monkeypatch, return_value=interpretation())
    context = await dc.build_dialogue_context(AsyncMock(), cid, rows[-1].content, rows=rows)
    state = {
        "latest_user_message": rows[-1].content,
        "dialogue_context": context,
        "text": "Original case facts",
        "turn_context": "Original case facts",
        "semantic": True,
        "stored": {"site_location": StoredFact("Kho A", True)},
        "pending_action": "draft_minutes",
    }
    rendered = intent.render_intent_prompt(state)
    assert rows[-1].content in rendered and interpretation()["interpreted_question"]["text"] in rendered
    assert help_reply._context_memories(state)["semantic_dialogue"]["analysis"] == context["analysis"]
    # A help exchange remains outside the fact planner and casual context.
    assert dc.context_for_prompt(state, scope="business")["status"] == "separate_dialogue_context"
    assert "Trợ lý đã hướng dẫn" not in str(planner._messages(state))
    assert "analysis" not in dc.context_for_prompt(state, scope="general")
    choice = IntentDecision(
        route=Route.SYSTEM_HELP, intent_label="help", confidence=0.99, help_topic_ids=[HelpTopic.MINUTES_INPUTS]
    )
    router = AsyncMock(return_value=IntentResult(choice, IntentFallback.NONE, None, 1, "test"))
    monkeypatch.setattr("src.agents.case_graph.route_turn", router)
    monkeypatch.setattr("src.agents.case_graph.format_help_reply", AsyncMock(return_value="Thông tin cần chuẩn bị"))
    forbidden = AsyncMock(side_effect=AssertionError("Interpretation must not call business tools"))
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", forbidden)
    result = await build_case_graph(forbidden, standalone=True).ainvoke(state)
    assert router.call_args.args[0]["dialogue_context"]["analysis"] == context["analysis"]
    assert result["latest_user_message"] == state["latest_user_message"]
    assert result["stored"] == state["stored"] and result["pending_action"] == "draft_minutes"
    assert result["state_update"] == "preserve" and result["task_change"] == "keep"
    forbidden.assert_not_awaited()
    assert interpretation()["interpreted_question"]["text"] in _resolved_question(state)
    state["dialogue_context"]["analysis"]["uncertainty"] = "Có hai cách hiểu"
    assert _resolved_question(state) == state["latest_user_message"]
