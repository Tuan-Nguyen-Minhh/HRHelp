"""Orchestration invariants across routes, workflows and model failures."""

from dataclasses import asdict, replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.exceptions import OutputParserException

from src.agents.case_graph import build_case_graph
from src.agents.conversation import TaskChange, memory_patch, recent_turns, working_specs
from src.core.config import settings
from src.features.clarify.model.assess import ClarifyPlan, StoredFact
from src.features.clarify.model.catalog import FactSpec
from src.features.clarify.model.decision import ClarifyDecision
from src.features.clarify.model.intent import IntentDecision, IntentFallback, IntentResult, Route, render_intent_prompt
from src.features.clarify.model.memory import _recent_messages, build_turn_context, update_memory
from src.features.clarify.model.planner import PlannerResult
from src.features.clarify.model.prompt import render_case_prompt

_SPECS = (
    FactSpec("site_location", "Địa điểm", "Sự việc xảy ra ở đâu?", source="ai_generated"),
    FactSpec("explanation_requested", "Giải trình", "Đã yêu cầu giải trình chưa?", source="ai_generated"),
    FactSpec("estimated_count", "Số lượng ước tính", "Nếu biết, số lượng là bao nhiêu?", required=False),
)
_WORKING = {"version": 1, "family": "custom_incident", "specs": [asdict(spec) for spec in _SPECS]}


def _memory(action="draft_minutes"):
    return SimpleNamespace(
        pending_action=action,
        pending_fact_keys=["site_location", "explanation_requested"],
        open_questions=[spec.question for spec in _SPECS[:2]],
        working_state=_WORKING,
        summary="Previous validated working state",
        last_user_intent="provide_facts",
        recent_messages=[],
    )


def _plan(state):
    return ClarifyPlan(
        family=state["family"],
        merged=state["merged"],
        missing_keys=state["missing_keys"],
        locked=state["facts_locked"],
        requested_action=state["requested_action"],
        user_intent=state["user_intent"],
        specs=tuple(state["specs"]),
        state_update=state["state_update"],
        task_change=state.get("task_change", "keep"),
    )


def _decision(**extra):
    return ClarifyDecision(
        family="GENERAL",
        family_confidence=0.1,
        confidence=0.95,
        user_intent="provide_facts",
        requested_action="complete_facts",
        **extra,
    )


def _pending_state(**extra):
    return {
        "semantic": True,
        "text": "CASE PROFILE\nCase for testing.\nRECENT_TURNS\nUSER: current reply",
        "latest_user_message": "Địa điểm là kho B. Đã yêu cầu giải trình bằng văn bản.",
        "stored": {},
        "family": "custom_incident",
        "active_specs": list(_SPECS),
        "pending_fact_keys": ["site_location", "explanation_requested"],
        "locked_fact_keys": [spec.key for spec in _SPECS],
        "pending_action": "draft_minutes",
        **extra,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["draft_minutes", "create_ticket_preview", "send_to_legal", "request_retrieval"])
async def test_invalid_router_output_preserves_pending_facts_for_every_workflow(monkeypatch, action):
    router = AsyncMock(side_effect=OutputParserException("malformed router JSON"))
    planner = AsyncMock(side_effect=AssertionError("A router failure does not authorize fact extraction"))
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("src.features.clarify.model.intent._complete", router)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", planner)
    retrieval = AsyncMock(side_effect=AssertionError("No retrieval was authorized"))
    result = await build_case_graph(retrieval).ainvoke(_pending_state(pending_action=action))
    assert router.await_count == 2
    assert result["intent_router_fallback_kind"] == "output"
    assert result["selected_route"] == Route.CLARIFY
    assert result["state_update"] == "preserve"
    assert result["specs"] == list(_SPECS)
    assert memory_patch(_plan(result), pending_action=action) == {}
    planner.assert_not_awaited()
    retrieval.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "route,action",
    [
        (Route.CASE_QA, ""),
        (Route.POLICY_QA, "answer_policy_question"),
        (Route.EXTERNAL_RESEARCH, "external_research"),
        (Route.CLARIFY, ""),
        (Route.UNSUPPORTED, "unsupported"),
        (Route.CAPABILITY_GAP, "capability_gap"),
    ],
)
async def test_side_routes_do_not_erase_another_tasks_working_state(monkeypatch, route, action):
    from datetime import date

    from src.features.external_research.model.tool import ExternalResearchResult

    router = AsyncMock(
        return_value=IntentResult(
            IntentDecision(route=route, confidence=0.99, intent_label="side_turn", requested_action=action),
            IntentFallback.NONE,
            None,
            1,
            "test",
        )
    )
    monkeypatch.setattr("src.agents.case_graph.route_turn", router)
    monkeypatch.setattr("src.agents.case_graph.answer_case_question", AsyncMock(return_value="Thông tin hồ sơ"))
    monkeypatch.setattr("src.agents.case_graph.answer_policy_question", AsyncMock(return_value="Quy định được hỏi"))
    monkeypatch.setattr("src.agents.case_graph.answer_external_research", AsyncMock(return_value="Nguồn công khai"))
    planner = AsyncMock(side_effect=AssertionError("Side questions do not collect facts"))
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", planner)
    external = AsyncMock(return_value=ExternalResearchResult(query="test", provider="test", sources=[]))
    result = await build_case_graph(AsyncMock(return_value=[]), external_research=external).ainvoke(
        _pending_state(
            latest_user_message="Một câu hỏi riêng.", incident_date=date(2026, 10, 10), agent_run_id=uuid4()
        ),
    )
    memory = _memory()
    before = dict(vars(memory))
    monkeypatch.setattr("src.features.clarify.model.memory.ensure_memory", AsyncMock(return_value=memory))
    monkeypatch.setattr("src.features.clarify.model.memory._recent_messages", AsyncMock(return_value=[]))
    await update_memory(AsyncMock(), uuid4(), _plan(result), result["question"])
    assert vars(memory) == before
    assert result["state_update"] == "preserve"
    planner.assert_not_awaited()


@pytest.mark.asyncio
async def test_both_model_failures_preserve_schema_questions_and_goal(monkeypatch):
    from src.features.clarify.model.planner import fallback_decision

    monkeypatch.setattr(
        "src.agents.case_graph.route_turn",
        AsyncMock(
            return_value=IntentResult(
                IntentDecision(route=Route.CLARIFY, intent_label="router_output_error", confidence=0),
                IntentFallback.OUTPUT,
                "invalid",
                1,
                "test",
            )
        ),
    )
    monkeypatch.setattr(
        "src.features.clarify.model.graph.plan_turn",
        AsyncMock(
            return_value=PlannerResult(
                fallback_decision(),
                True,
                "invalid",
                1,
                "test",
            )
        ),
    )
    result = await build_case_graph(AsyncMock()).ainvoke(_pending_state(latest_user_message="kho B"))
    assert result["state_update"] == "preserve"
    assert memory_patch(_plan(result)) == {}
    assert result["specs"] == list(_SPECS)
    assert result.get("handoff") is None


@pytest.mark.asyncio
async def test_new_workflow_replaces_goal_without_overriding_the_fact_schema(monkeypatch):
    monkeypatch.setattr(
        "src.agents.case_graph.route_turn",
        AsyncMock(
            return_value=IntentResult(
                IntentDecision(
                    route=Route.WORKFLOW_ACTION,
                    intent_label="new_goal",
                    confidence=0.99,
                    requested_action="create_ticket_preview",
                    task_change=TaskChange.REPLACE,
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
        AsyncMock(
            return_value=PlannerResult(
                _decision(),
                False,
                None,
                1,
                "test",
            )
        ),
    )
    result = await build_case_graph(AsyncMock()).ainvoke(_pending_state(latest_user_message="Chuyển sang tạo phiếu."))
    patch = memory_patch(_plan(result))
    assert patch["pending_action"] == "create_ticket_preview"
    assert patch["pending_fact_keys"] == ["site_location", "explanation_requested"]
    assert working_specs(patch["working_state"]) == _SPECS


@pytest.mark.asyncio
async def test_explicit_cancel_clears_only_pending_task_and_keeps_facts(monkeypatch):
    monkeypatch.setattr(
        "src.agents.case_graph.route_turn",
        AsyncMock(
            return_value=IntentResult(
                IntentDecision(
                    route=Route.CLARIFY, intent_label="cancel_task", confidence=0.99, task_change=TaskChange.CANCEL
                ),
                IntentFallback.NONE,
                None,
                1,
                "test",
            )
        ),
    )
    planner = AsyncMock(side_effect=AssertionError("Cancelled work must not run"))
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", planner)
    stored = {"site_location": StoredFact("kho B", True)}
    result = await build_case_graph(AsyncMock()).ainvoke(
        _pending_state(latest_user_message="Hủy việc đang làm.", stored=stored)
    )
    assert result["merged"] == stored
    assert memory_patch(_plan(result)) == {"pending_action": None, "pending_fact_keys": [], "open_questions": []}
    planner.assert_not_awaited()


@pytest.mark.asyncio
async def test_output_failure_without_pending_work_reports_processing_error(monkeypatch):
    monkeypatch.setattr(
        "src.agents.case_graph.route_turn",
        AsyncMock(
            return_value=IntentResult(
                IntentDecision(route=Route.CLARIFY, intent_label="router_output_error", confidence=0),
                IntentFallback.OUTPUT,
                "invalid",
                1,
                "test",
            )
        ),
    )
    planner = AsyncMock(side_effect=AssertionError("No pending questions to recover"))
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", planner)
    result = await build_case_graph(AsyncMock()).ainvoke(
        {"semantic": True, "latest_user_message": "Một yêu cầu.", "stored": {}}
    )
    assert "lỗi xử lý" in result["question"]
    assert "chưa chắc mục tiêu" not in result["question"]
    assert memory_patch(_plan(result)) == {}


@pytest.mark.asyncio
async def test_long_user_answer_survives_storage_context_and_both_prompts(monkeypatch):
    answer = "Thông tin ban đầu. " * 600 + "Đã yêu cầu giải trình bằng văn bản."
    row = SimpleNamespace(role="USER", content=answer, created_at=None)
    monkeypatch.setattr("src.features.clarify.model.memory.list_messages", AsyncMock(return_value=[row]))
    messages = await _recent_messages(AsyncMock(), uuid4())
    assert messages[0]["content"] == answer
    memory = _memory()
    monkeypatch.setattr("src.features.clarify.model.memory.get_memory", AsyncMock(return_value=memory))
    context = await build_turn_context(AsyncMock(), uuid4(), "Incident", {})
    assert answer in context
    assert "PENDING_FACT_KEYS" in context
    assert "CASE DESCRIPTION" in render_intent_prompt({"turn_context": context})
    assert answer in render_intent_prompt({"turn_context": context})
    assert answer in render_case_prompt(context, [])


def test_context_budget_omits_whole_old_messages_and_preserves_latest_answer():
    assert (
        recent_turns(
            [
                {"role": "USER", "content": "old " * 100},
                {"role": "USER", "content": "latest answer has its final value"},
            ],
            budget=20,
        )
        == "USER: latest answer has its final value"
    )


def test_omitted_model_requirements_cannot_change_optional_fields_or_questions():
    from src.features.clarify.model.policy import apply_decision

    plan = apply_decision(
        "kho B",
        {},
        _decision(
            fact_requirements=[
                {
                    "key": "estimated_count",
                    "label": "Changed",
                    "question": "New question",
                    "required": True,
                }
            ]
        ),
        active_specs=_SPECS,
        active_family="custom_incident",
    )
    assert plan.specs == _SPECS
    assert "estimated_count" not in plan.missing_keys
    assert memory_patch(replace(plan, state_update="preserve")) == {}


@pytest.mark.parametrize("completed", [False, True])
def test_another_action_cannot_replace_or_complete_pending_work_without_explicit_transition(completed):
    plan = ClarifyPlan("custom_incident", {}, [], True, requested_action="request_retrieval", specs=_SPECS)
    patch = memory_patch(plan, pending_action="draft_minutes", action_completed=completed)
    assert "pending_action" not in patch
    patch = memory_patch(
        replace(plan, task_change="replace"), pending_action="draft_minutes", action_completed=completed
    )
    assert patch["pending_action"] == (None if completed else "request_retrieval")


@pytest.mark.asyncio
async def test_internal_handoffs_do_not_displace_user_messages_in_the_recent_window(monkeypatch):
    user = SimpleNamespace(role="USER", content="Complete user answer", created_at=None)
    internal = [
        SimpleNamespace(role="ASSISTANT", content="internal JSON", message_metadata={"internal": True})
        for _ in range(10)
    ]
    monkeypatch.setattr("src.features.clarify.model.memory.list_messages", AsyncMock(return_value=[user, *internal]))
    assert (await _recent_messages(AsyncMock(), uuid4())) == [
        {"role": "USER", "content": user.content, "created_at": ""}
    ]


@pytest.mark.asyncio
async def test_retrieval_handoff_keeps_the_validated_schema_and_optional_facts(monkeypatch):
    from datetime import date

    from src.features.clarify.model.turns import _locked_facts

    stored = {
        "site_location": StoredFact("kho B", True),
        "explanation_requested": StoredFact("true", True),
        "estimated_count": StoredFact("500", True),
    }
    planner = AsyncMock(side_effect=AssertionError("Validated handoffs must not run another interpretation"))
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", planner)
    result = await build_case_graph(AsyncMock(return_value=[])).ainvoke(
        _pending_state(
            step="cite",
            stored=stored,
            incident_date=date(2026, 10, 10),
            agent_run_id=uuid4(),
            text="Old history says site_location=other place",
        )
    )
    assert result["handoff"].family == "custom_incident"
    assert result["handoff"].facts == {key: fact.value for key, fact in stored.items()}
    assert _locked_facts(_plan(result)) == result["handoff"].facts
    planner.assert_not_awaited()


@pytest.mark.asyncio
async def test_reading_facts_projects_memory_without_routing_history(monkeypatch):
    from src.features.clarify.model import turns

    stored = {"site_location": StoredFact("kho B", True)}
    monkeypatch.setattr(turns, "_stored", AsyncMock(return_value=stored))
    monkeypatch.setattr(turns, "_transcript", AsyncMock(return_value="Old workflow command"))
    monkeypatch.setattr(turns, "_locked_fact_keys", AsyncMock(return_value=[spec.key for spec in _SPECS]))
    monkeypatch.setattr(turns, "get_memory", AsyncMock(return_value=_memory()))
    router = AsyncMock(side_effect=AssertionError("GET/read projection must not run routing or model calls"))
    monkeypatch.setattr(turns, "build_case_graph", router)
    plan, handoff = await turns._plan(
        AsyncMock(), SimpleNamespace(id=uuid4(), description="Incident"), uuid4(), semantic=True
    )
    assert plan.missing_keys == ["explanation_requested"]
    assert plan.specs == _SPECS
    assert plan.merged == stored
    assert plan.state_update == "preserve"
    assert handoff is None
    router.assert_not_called()
