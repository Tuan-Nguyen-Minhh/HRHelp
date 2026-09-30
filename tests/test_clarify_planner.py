"""Semantic planner decisions stay behind Python validation and routing."""

from datetime import date
from uuid import uuid4

import pytest

from src.agents.case_graph import build_case_graph
from src.core.config import settings
from src.features.cite.model.query import SearchQuery
from src.features.clarify.model.assess import StoredFact
from src.features.clarify.model.catalog import ABSENCE, GENERAL
from src.features.clarify.model.decision import (
    CaseFamily,
    ClarifyDecision,
    ConfirmationUpdate,
    ExtractedFact,
    RequestedAction,
    UserIntent,
)
from src.features.clarify.model.graph import route_after_extract
from src.features.clarify.model.planner import plan_turn
from src.features.clarify.model.policy import apply_decision
from src.features.clarify.model.prompt import PROMPT_VERSION, SYSTEM_PROMPT, render_case_prompt

_ABSENCE_STORED = {
    "contract_type": StoredFact("xác định thời hạn", True),
    "absence_days": StoredFact("5 ngày", True),
    "notice_form": StoredFact("không báo", True),
    "minutes_made": StoredFact("true", True),
    "explanation_requested": StoredFact("true", True),
}


def _fact(key: str, value: str, evidence: str, confidence: float = 0.95, ambiguous: bool = False) -> ExtractedFact:
    return ExtractedFact(key=key, value=value, confidence=confidence, evidence=evidence, ambiguous=ambiguous)


def _decision(**overrides) -> ClarifyDecision:
    payload = {
        "family": CaseFamily.UNAUTHORIZED_ABSENCE,
        "family_confidence": 0.95,
        "extracted_facts": [],
        "confirmation_updates": [],
        "corrections": [],
        "user_intent": UserIntent.PROVIDE_FACTS,
        "requested_action": RequestedAction.NEED_CLARIFICATION,
        "ambiguities": [],
        "confidence": 0.9,
        "reasoning_summary": None,
    }
    payload.update(overrides)
    return ClarifyDecision(**payload)


def _state(plan, **extra) -> dict:
    state = {
        "family": plan.family,
        "facts_locked": plan.locked,
        "conflicts": [
            {"key": item.key, "confirmed_value": item.confirmed_value, "proposed_value": item.proposed_value}
            for item in plan.conflicts
        ],
        "requested_action": plan.requested_action,
        "planner_fallback": plan.planner_fallback,
    }
    state.update(extra)
    return state


def test_prompt_keeps_the_planner_off_the_graph_edge():
    assert PROMPT_VERSION == "clarify-planner-v1"
    assert "Never invent missing facts" in SYSTEM_PROMPT
    assert "LangGraph" in SYSTEM_PROMPT
    rendered = render_case_prompt("nghỉ 5 ngày", ["absence_days = 5 ngày [pending]"])
    assert "absence_days" in rendered
    assert "UNAUTHORIZED_ABSENCE" in rendered
    assert "CURRENT STORED FACTS" in rendered


def test_direct_fact_does_not_fill_the_rest_of_the_catalog():
    plan = apply_decision(
        "Nhân viên nghỉ không phép 5 ngày.",
        {},
        _decision(
            extracted_facts=[_fact("absence_days", "5 ngày", "nghỉ không phép 5 ngày")],
        ),
    )
    assert plan.family == ABSENCE
    assert plan.merged["absence_days"].value == "5 ngày"
    assert plan.merged["absence_days"].confirmed is False
    assert "contract_type" not in plan.merged
    assert "minutes_made" not in plan.merged
    assert route_after_extract(_state(plan)) == "ask"


def test_natural_absence_phrase_maps_days_and_notice():
    plan = apply_decision(
        "Anh A tự ý nghỉ 5 hôm mà chẳng báo cho quản lý.",
        {},
        _decision(
            extracted_facts=[
                _fact("absence_days", "5", "nghỉ 5 hôm"),
                _fact("notice_form", "none", "chẳng báo cho quản lý"),
            ]
        ),
    )
    assert plan.merged["absence_days"].value == "5 ngày"
    assert plan.merged["notice_form"].value == "không báo"
    assert plan.merged["absence_days"].confirmed is False
    assert route_after_extract(_state(plan)) == "ask"


def test_one_message_can_carry_several_catalog_facts():
    plan = apply_decision(
        "Nhân viên nghỉ 5 ngày, hợp đồng xác định thời hạn và đã được yêu cầu giải trình.",
        {},
        _decision(
            extracted_facts=[
                _fact("absence_days", "5 ngày", "nghỉ 5 ngày"),
                _fact("contract_type", "fixed_term", "hợp đồng xác định thời hạn"),
                _fact("explanation_requested", "true", "đã được yêu cầu giải trình"),
            ]
        ),
    )
    assert plan.merged["absence_days"].value == "5 ngày"
    assert plan.merged["contract_type"].value == "xác định thời hạn"
    assert plan.merged["explanation_requested"].value == "true"
    assert plan.merged["explanation_requested"].confirmed is False
    assert "notice_form" in plan.missing_keys
    assert route_after_extract(_state(plan)) == "ask"


def test_confirmed_value_stays_when_the_user_states_a_different_one():
    stored = {"absence_days": StoredFact("5 ngày", True)}
    plan = apply_decision(
        "Không phải 5 ngày, là 7 ngày.",
        stored,
        _decision(
            user_intent=UserIntent.CORRECT_FACTS,
            corrections=[_fact("absence_days", "7 ngày", "là 7 ngày")],
        ),
    )
    assert plan.merged["absence_days"].value == "5 ngày"
    assert plan.merged["absence_days"].confirmed is True
    assert plan.conflicts[0].proposed_value == "7 ngày"
    assert plan.locked is False
    assert route_after_extract(_state(plan)) == "ask"


def test_explicit_confirmation_can_replace_a_confirmed_value():
    stored = {"absence_days": StoredFact("5 ngày", True)}
    plan = apply_decision(
        "Tôi xác nhận lại: không phải 5 ngày, là 7 ngày.",
        stored,
        _decision(
            user_intent=UserIntent.CORRECT_FACTS,
            corrections=[_fact("absence_days", "7 ngày", "là 7 ngày")],
            confirmation_updates=[ConfirmationUpdate(key="absence_days", confirmed=True)],
        ),
    )
    assert plan.merged["absence_days"].value == "7 ngày"
    assert plan.merged["absence_days"].confirmed is True
    assert plan.conflicts == ()


def test_pending_fact_is_confirmed_only_when_the_user_accepts_it():
    stored = {"absence_days": StoredFact("5 ngày", False)}
    plan = apply_decision(
        "Đúng rồi, 5 ngày.",
        stored,
        _decision(
            user_intent=UserIntent.CONFIRM_FACTS,
            confirmation_updates=[ConfirmationUpdate(key="absence_days", confirmed=True)],
        ),
    )
    assert plan.merged["absence_days"].value == "5 ngày"
    assert plan.merged["absence_days"].confirmed is True


def test_a_new_fact_stays_pending_even_if_the_model_marks_it_confirmed():
    plan = apply_decision(
        "Nhân viên nghỉ không phép 5 ngày.",
        {},
        _decision(
            user_intent=UserIntent.PROVIDE_FACTS,
            extracted_facts=[_fact("absence_days", "5 ngày", "nghỉ không phép 5 ngày")],
            confirmation_updates=[ConfirmationUpdate(key="absence_days", confirmed=True)],
        ),
    )
    assert plan.merged["absence_days"].confirmed is False


def test_vague_duration_does_not_become_a_number():
    plan = apply_decision(
        "Anh ấy nghỉ khá nhiều.",
        {},
        _decision(
            extracted_facts=[_fact("absence_days", "5", "khá nhiều", confidence=0.9)],
            ambiguities=["absence_days"],
        ),
    )
    assert "absence_days" not in plan.merged
    assert route_after_extract(_state(plan)) == "ask"


def test_ambiguous_flag_drops_the_value():
    plan = apply_decision(
        "Anh ấy nghỉ nhiều ngày.",
        {},
        _decision(extracted_facts=[_fact("absence_days", "", "nghỉ nhiều ngày", ambiguous=True)]),
    )
    assert "absence_days" not in plan.merged


def test_unknown_fact_key_is_ignored():
    plan = apply_decision(
        "Nhân viên nghỉ không phép 5 ngày.",
        {},
        _decision(
            extracted_facts=[
                _fact("employee_attitude", "kém", "kém"),
                _fact("absence_days", "5 ngày", "nghỉ không phép 5 ngày"),
            ]
        ),
    )
    assert "employee_attitude" not in plan.merged
    assert plan.merged["absence_days"].value == "5 ngày"
    assert plan.validation.startswith("ignored=employee_attitude")


def test_low_family_confidence_uses_general_when_no_fact_is_present():
    plan = apply_decision(
        "Xin chào",
        {},
        _decision(family=CaseFamily.UNAUTHORIZED_ABSENCE, family_confidence=0.2, confidence=0.2),
    )
    assert plan.family == GENERAL


def test_confirmed_family_is_not_replaced_by_a_confident_guess():
    plan = apply_decision(
        "Đi muộn 2 ngày.",
        _ABSENCE_STORED,
        _decision(
            family=CaseFamily.LATE,
            family_confidence=0.99,
            extracted_facts=[_fact("late_days", "2 ngày", "2 ngày")],
        ),
    )
    assert plan.family == ABSENCE
    assert "late_days" not in plan.merged
    assert plan.merged["absence_days"].value == "5 ngày"


def test_explicit_key_line_is_kept_when_the_planner_returns_nothing():
    plan = apply_decision(
        "absence_days: 5 ngày trong 30 ngày",
        {},
        _decision(family_confidence=0, extracted_facts=[]),
        fallback=True,
    )
    assert plan.merged["absence_days"].value == "5 ngày trong 30 ngày"
    assert plan.merged["absence_days"].confirmed is False
    assert plan.planner_fallback is True
    assert route_after_extract(_state(plan)) == "ask"


def test_retrieval_request_is_ignored_until_facts_are_locked():
    plan = apply_decision(
        "Hãy tra quy định xử lý trường hợp này.",
        {"absence_days": StoredFact("5 ngày", True)},
        _decision(
            user_intent=UserIntent.REQUEST_CONSULTATION,
            requested_action=RequestedAction.REQUEST_RETRIEVAL,
        ),
    )
    assert plan.locked is False
    assert route_after_extract(_state(plan, incident_date=date(2026, 3, 1), agent_run_id=uuid4())) == "ask"


def test_locked_facts_retrieve_only_for_a_retrieval_request():
    plan = apply_decision(
        "Hãy tra quy định.",
        _ABSENCE_STORED,
        _decision(
            user_intent=UserIntent.REQUEST_CONSULTATION,
            requested_action=RequestedAction.REQUEST_RETRIEVAL,
        ),
    )
    assert plan.locked is True
    assert route_after_extract(_state(plan)) == "done"
    assert route_after_extract(_state(plan, incident_date=date(2026, 3, 1), agent_run_id=uuid4())) == "retrieve"


def test_complete_facts_without_a_retrieval_request_stop():
    plan = apply_decision(
        "Đã đủ.",
        _ABSENCE_STORED,
        _decision(user_intent=UserIntent.CONFIRM_FACTS, requested_action=RequestedAction.COMPLETE_FACTS),
    )
    assert plan.locked is True
    assert route_after_extract(_state(plan, incident_date=date(2026, 3, 1), agent_run_id=uuid4())) == "done"


def test_a_raw_edge_name_does_not_retrieve():
    plan = apply_decision("Đã đủ.", _ABSENCE_STORED, _decision())
    state = _state(plan, incident_date=date(2026, 3, 1), agent_run_id=uuid4(), requested_action="retrieve")
    assert route_after_extract(state) == "done"


def test_cite_step_still_retrieves_from_locked_facts():
    assert route_after_extract({"facts_locked": True, "step": "cite", "conflicts": []}) == "retrieve"
    assert route_after_extract({"facts_locked": False, "step": "cite"}) == "ask"


def test_planner_fallback_keeps_obvious_facts_and_still_asks():
    plan = apply_decision(
        "Nhân viên hợp đồng xác định thời hạn nghỉ không phép 5 ngày trong 30 ngày, không báo. "
        "Đã lập biên bản. Chưa gửi yêu cầu giải trình.",
        {},
        _decision(family_confidence=0, confidence=0),
        fallback=True,
    )
    assert "5" in plan.merged["absence_days"].value
    assert "30" in plan.merged["absence_days"].value
    assert plan.merged["notice_form"].value == "không báo"
    assert plan.merged["minutes_made"].value == "true"
    assert plan.merged["explanation_requested"].value == "false"
    assert plan.merged["absence_days"].confirmed is False
    assert plan.locked is False
    assert route_after_extract(_state(plan, incident_date=date(2026, 3, 1), agent_run_id=uuid4())) == "ask"


def test_fallback_does_not_retrieve_a_locked_case():
    plan = apply_decision("tra quy định", _ABSENCE_STORED, _decision(), fallback=True)
    state = _state(
        plan,
        incident_date=date(2026, 3, 1),
        agent_run_id=uuid4(),
        requested_action="request_retrieval",
    )
    assert state["planner_fallback"] is True
    assert route_after_extract(state) == "done"


@pytest.mark.asyncio
async def test_planner_failure_falls_back_to_ask(monkeypatch):
    async def boom(_messages, _attempt):
        raise TimeoutError("slow")

    monkeypatch.setattr(settings, "XAI_API_KEY", "test-key")
    monkeypatch.setattr("src.features.clarify.model.planner._complete", boom)
    result = await plan_turn({"text": "Nhân viên tự ý nghỉ.", "stored": {}})
    assert result.fallback is True
    assert result.reason == "TimeoutError"
    assert result.decision.requested_action is RequestedAction.NEED_CLARIFICATION
    plan = apply_decision("Nhân viên tự ý nghỉ.", {}, result.decision, fallback=True)
    assert route_after_extract(_state(plan, incident_date=date(2026, 3, 1), agent_run_id=uuid4())) == "ask"


@pytest.mark.asyncio
async def test_invalid_decision_is_retried_once(monkeypatch):
    calls = {"n": 0}

    async def flaky(_messages, _attempt):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("schema")
        return _decision(extracted_facts=[_fact("absence_days", "5 ngày", "5 ngày")])

    monkeypatch.setattr(settings, "XAI_API_KEY", "test-key")
    monkeypatch.setattr("src.features.clarify.model.planner._complete", flaky)
    result = await plan_turn({"text": "nghỉ 5 ngày", "stored": {}})
    assert calls["n"] == 2
    assert result.fallback is False
    assert result.decision.extracted_facts[0].key == "absence_days"


@pytest.mark.asyncio
async def test_missing_api_key_does_not_call_the_model(monkeypatch):
    async def boom(_messages, _attempt):
        raise AssertionError("the model must not be called")

    monkeypatch.setattr(settings, "XAI_API_KEY", "")
    monkeypatch.setattr("src.features.clarify.model.planner._complete", boom)
    result = await plan_turn({"text": "nghỉ 5 ngày", "stored": {}})
    assert result.fallback is True
    assert result.reason == "missing_api_key"


@pytest.mark.asyncio
async def test_graph_retrieves_when_a_locked_case_asks_for_rules(monkeypatch):
    seen = {"calls": 0}

    async def search(_query: SearchQuery):
        seen["calls"] += 1
        return []

    async def fake(_state):
        from src.features.clarify.model.planner import PlannerResult

        return PlannerResult(
            _decision(
                user_intent=UserIntent.REQUEST_CONSULTATION,
                requested_action=RequestedAction.REQUEST_RETRIEVAL,
            ),
            False,
            None,
            1,
            "grok-4.7",
        )

    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", fake)
    state = await build_case_graph(search).ainvoke(
        {
            "semantic": True,
            "text": "Hãy tra quy định xử lý.",
            "stored": _ABSENCE_STORED,
            "description": "nghỉ không phép",
            "incident_date": date(2026, 3, 1),
            "agent_run_id": uuid4(),
            "employee_name": "An",
        }
    )
    assert seen["calls"] == 1
    assert state["handoff"].family == ABSENCE
    assert state["facts_locked"] is True


@pytest.mark.asyncio
async def test_graph_asks_when_retrieval_is_requested_too_early(monkeypatch):
    async def search(_query: SearchQuery):
        raise AssertionError("open facts must not retrieve")

    async def fake(_state):
        from src.features.clarify.model.planner import PlannerResult

        return PlannerResult(
            _decision(requested_action=RequestedAction.REQUEST_RETRIEVAL),
            False,
            None,
            1,
            "grok-4.7",
        )

    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", fake)
    state = await build_case_graph(search).ainvoke(
        {
            "semantic": True,
            "text": "Nhân viên tự ý nghỉ. Hãy tra quy định.",
            "stored": {},
            "incident_date": date(2026, 3, 1),
            "agent_run_id": uuid4(),
        }
    )
    assert state["facts_locked"] is False
    assert "Hợp đồng" in state["question"]
    assert state.get("handoff") is None
