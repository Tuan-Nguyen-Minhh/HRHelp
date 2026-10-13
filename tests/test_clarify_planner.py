"""Semantic planner decisions stay behind Python validation and routing."""

from datetime import date
from uuid import uuid4

import pytest

from src.agents.case_graph import build_case_graph, route_after_intent
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
from src.features.clarify.model.intent import (
    IntentDecision,
    IntentFallback,
    IntentResult,
    IntentTarget,
    Route,
    render_intent_prompt,
    route_turn,
)
from src.features.clarify.model.memory import build_turn_context
from src.features.clarify.model.planner import plan_turn
from src.features.clarify.model.policy import apply_decision
from src.features.clarify.model.prompt import PROMPT_VERSION, SYSTEM_PROMPT, render_case_prompt
from src.features.external_research.model.answer import EXTERNAL_RESEARCH_DISCLAIMER
from src.features.external_research.model.tool import ExternalResearchQuery, ExternalResearchResult, ExternalSource

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
    assert PROMPT_VERSION == "clarify-planner-v4-dynamic-facts"
    assert "Never invent missing facts" in SYSTEM_PROMPT
    assert "LangGraph" in SYSTEM_PROMPT
    assert "lập biên bản" in SYSTEM_PROMPT
    assert "fact_requirements" in SYSTEM_PROMPT
    rendered = render_case_prompt("nghỉ 5 ngày", ["absence_days = 5 ngày [pending]"])
    assert "absence_days" in rendered
    assert "UNAUTHORIZED_ABSENCE" in rendered
    assert "DYNAMIC FACT SCHEMA RULES" in rendered
    assert "CURRENT STORED FACTS" in rendered


def test_intent_prompt_separates_latest_message_from_turn_context():
    rendered = render_intent_prompt(
        {
            "latest_user_message": "nhân viên này vi phạm gì",
            "turn_context": "CASE DESCRIPTION\nVi phạm: tự ý nhận hoa hồng của khách",
            "stored": {},
        }
    )
    assert "LATEST_USER_MESSAGE\nnhân viên này vi phạm gì" in rendered
    assert "TURN_CONTEXT\nCASE DESCRIPTION" in rendered


@pytest.mark.asyncio
async def test_intent_router_schema_failure_asks_for_clarification(monkeypatch):
    async def invalid_output(_messages, _attempt, _model_name):
        raise ValueError("route outside schema")

    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("src.features.clarify.model.intent._complete", invalid_output)
    result = await route_turn({"text": "làm một việc lạ chưa có node", "stored": {}})
    assert result.fallback_kind is IntentFallback.SEMANTIC
    assert result.decision.route is Route.CLARIFY
    assert result.decision.intent_label == "unroutable_intent"


def test_dynamic_fact_schema_accepts_uncovered_case_requirements():
    plan = apply_decision(
        "Có khiếu nại quấy rối xảy ra ngày 10/10, nhân chứng là chị Lan.",
        {},
        _decision(
            family="harassment",
            fact_requirements=[
                {
                    "key": "incident_time",
                    "label": "Thời điểm xảy ra",
                    "question": "Vụ việc xảy ra khi nào?",
                    "required": True,
                },
                {
                    "key": "witnesses",
                    "label": "Nhân chứng",
                    "question": "Ai chứng kiến vụ việc?",
                    "required": True,
                },
            ],
            extracted_facts=[
                _fact("incident_time", "ngày 10/10", "ngày 10/10"),
                _fact("witnesses", "chị Lan", "nhân chứng là chị Lan"),
            ],
        ),
    )
    assert plan.family == "harassment"
    assert [spec.key for spec in plan.specs] == ["incident_time", "witnesses"]
    assert plan.missing_keys == []
    assert plan.locked is True


def test_locked_dynamic_schema_ignores_new_requirements_on_followup():
    plan = apply_decision(
        "Nhân chứng là chị Lan. Ngoài ra planner thử đòi thêm camera.",
        {"incident_time": StoredFact("ngày 10/10", True)},
        _decision(
            family="harassment",
            fact_requirements=[
                {
                    "key": "incident_time",
                    "label": "Thời điểm xảy ra",
                    "question": "Vụ việc xảy ra khi nào?",
                    "required": True,
                },
                {
                    "key": "witnesses",
                    "label": "Nhân chứng",
                    "question": "Ai chứng kiến vụ việc?",
                    "required": True,
                },
                {
                    "key": "camera_footage",
                    "label": "Camera",
                    "question": "Có camera không?",
                    "required": True,
                },
            ],
            extracted_facts=[
                _fact("witnesses", "chị Lan", "Nhân chứng là chị Lan"),
                _fact("camera_footage", "có", "camera"),
            ],
        ),
        locked_keys={"incident_time", "witnesses"},
    )
    assert [spec.key for spec in plan.specs] == ["incident_time", "witnesses"]
    assert "camera_footage" not in plan.merged
    assert plan.missing_keys == []
    assert plan.locked is True


def test_locked_dynamic_schema_requires_human_confirmation_for_critical_amendment():
    plan = apply_decision(
        "Người này vi phạm cách đây 20 hôm trước.",
        {"witnesses": StoredFact("chị Lan", True)},
        _decision(
            family="harassment",
            fact_requirements=[
                {
                    "key": "witnesses",
                    "label": "Nhân chứng",
                    "question": "Ai chứng kiến vụ việc?",
                    "required": True,
                },
                {
                    "key": "violation_date",
                    "label": "Thời điểm vi phạm",
                    "question": "Người này vi phạm khi nào?",
                    "required": True,
                },
            ],
            extracted_facts=[
                _fact("violation_date", "cách đây 20 hôm trước", "vi phạm cách đây 20 hôm trước"),
            ],
        ),
        locked_keys={"witnesses"},
    )
    assert [spec.key for spec in plan.specs] == ["witnesses", "violation_date"]
    assert plan.merged["violation_date"] == StoredFact("cách đây 20 hôm trước", False)
    assert plan.missing_keys == []
    assert plan.locked is False


def test_minutes_request_keeps_draft_action_even_when_facts_are_missing():
    plan = apply_decision(
        "lập biên bản vi phạm cho tôi",
        {},
        _decision(requested_action=RequestedAction.ANSWER_POLICY_QUESTION),
    )
    assert plan.requested_action == "draft_minutes"
    assert plan.locked is False
    assert route_after_extract(_state(plan, incident_date=date(2026, 3, 1), agent_run_id=uuid4())) == "ask"


def test_route_after_intent_uses_python_policy():
    assert (
        route_after_intent(
            {
                "intent_decision": IntentDecision(
                    route=Route.CASE_QA,
                    intent_label="ask_case_profile",
                    target=IntentTarget.CASE_PROFILE,
                    confidence=0.9,
                )
            }
        )
        == "case_qa"
    )
    assert (
        route_after_intent(
            {
                "intent_decision": IntentDecision(
                    route=Route.POLICY_QA,
                    intent_label="ask_internal_policy",
                    target=IntentTarget.INTERNAL_POLICY,
                    confidence=0.9,
                    requires_internal_retrieval=True,
                )
            }
        )
        == "action"
    )
    assert (
        route_after_intent(
            {
                "intent_decision": IntentDecision(
                    route=Route.CASE_QA,
                    intent_label="ask_case_profile",
                    target=IntentTarget.CASE_PROFILE,
                    confidence=0.2,
                )
            }
        )
        == "disambiguate"
    )


def test_route_after_intent_keeps_open_labels_behind_closed_routes():
    assert (
        route_after_intent(
            {
                "intent_decision": IntentDecision(
                    route=Route.CAPABILITY_GAP,
                    intent_label="calculate_litigation_probability",
                    raw_intent_label="estimate lawsuit risk",
                    capability_needed="legal_risk_calculator",
                    confidence=0.88,
                )
            }
        )
        == "action"
    )
    assert route_after_intent({"intent_router_fallback_kind": IntentFallback.SEMANTIC.value}) == "disambiguate"
    assert route_after_intent({"intent_router_fallback_kind": IntentFallback.TECHNICAL.value}) == "extract"


@pytest.mark.asyncio
async def test_turn_context_includes_case_profile_for_planner_memory():
    context = await build_turn_context(
        object(),
        None,
        "Nhân viên bị tố cáo tiết lộ dữ liệu khách hàng.",
        {},
        case_code="CASE-001",
        employee_name="Nguyễn Văn A",
        employee_code="E001",
        incident_date=date(2026, 3, 1),
    )
    assert "CASE PROFILE" in context
    assert "case_code: CASE-001" in context
    assert "employee_name: Nguyễn Văn A" in context
    assert "employee_code: E001" in context
    assert "incident_date: 2026-03-01" in context
    assert "CASE DESCRIPTION" in context


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
    assert plan.merged["absence_days"].confirmed is True
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
    assert plan.merged["absence_days"].confirmed is True
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
    assert plan.merged["explanation_requested"].confirmed is True
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
    assert plan.merged["absence_days"].value == "7 ngày"
    assert plan.merged["absence_days"].confirmed is True
    assert plan.conflicts == ()
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


def test_a_new_fact_is_accepted_without_a_separate_confirmation():
    plan = apply_decision(
        "Nhân viên nghỉ không phép 5 ngày.",
        {},
        _decision(
            user_intent=UserIntent.PROVIDE_FACTS,
            extracted_facts=[_fact("absence_days", "5 ngày", "nghỉ không phép 5 ngày")],
            confirmation_updates=[ConfirmationUpdate(key="absence_days", confirmed=True)],
        ),
    )
    assert plan.merged["absence_days"].confirmed is True


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
    assert plan.merged["absence_days"].confirmed is True
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
    assert route_after_extract(_state(plan, incident_date=date(2026, 3, 1), agent_run_id=uuid4())) == "retrieve"


def test_a_raw_edge_name_does_not_decide_the_route():
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
    assert plan.merged["absence_days"].confirmed is True
    assert plan.locked is True
    assert route_after_extract(_state(plan, incident_date=date(2026, 3, 1), agent_run_id=uuid4())) == "retrieve"


def test_fallback_retrieves_when_the_required_facts_are_present():
    plan = apply_decision("tra quy định", _ABSENCE_STORED, _decision(), fallback=True)
    state = _state(
        plan,
        incident_date=date(2026, 3, 1),
        agent_run_id=uuid4(),
        requested_action="request_retrieval",
    )
    assert state["planner_fallback"] is True
    assert route_after_extract(state) == "retrieve"


@pytest.mark.asyncio
async def test_planner_failure_falls_back_to_ask(monkeypatch):
    async def boom(_messages, _attempt, _model_name):
        raise TimeoutError("slow")

    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("src.features.clarify.model.planner._complete", boom)
    result = await plan_turn({"text": "Nhân viên tự ý nghỉ.", "stored": {}})
    assert result.fallback is True
    assert result.reason == f"{settings.chat_models()[-1]}: TimeoutError"
    assert result.decision.requested_action is RequestedAction.NEED_CLARIFICATION
    plan = apply_decision("Nhân viên tự ý nghỉ.", {}, result.decision, fallback=True)
    assert route_after_extract(_state(plan, incident_date=date(2026, 3, 1), agent_run_id=uuid4())) == "ask"


@pytest.mark.asyncio
async def test_invalid_decision_is_retried_once(monkeypatch):
    calls = {"n": 0}

    async def flaky(_messages, _attempt, _model_name):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("schema")
        return _decision(extracted_facts=[_fact("absence_days", "5 ngày", "5 ngày")])

    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("src.features.clarify.model.planner._complete", flaky)
    result = await plan_turn({"text": "nghỉ 5 ngày", "stored": {}})
    assert calls["n"] == 2
    assert result.fallback is False
    assert result.decision.extracted_facts[0].key == "absence_days"


@pytest.mark.asyncio
async def test_missing_api_key_does_not_call_the_model(monkeypatch):
    async def boom(_messages, _attempt, _model_name):
        raise AssertionError("the model must not be called")

    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr("src.features.clarify.model.planner._complete", boom)
    result = await plan_turn({"text": "nghỉ 5 ngày", "stored": {}})
    assert result.fallback is True
    assert result.reason == "missing_api_key"


@pytest.mark.asyncio
async def test_graph_routes_case_question_before_fact_planning(monkeypatch):
    async def search(_query: SearchQuery):
        raise AssertionError("case profile questions must not retrieve")

    async def fake_intent(_state):
        return IntentResult(
            IntentDecision(
                route=Route.CASE_QA,
                intent_label="ask_case_profile",
                target=IntentTarget.CASE_PROFILE,
                confidence=0.94,
                requires_fact_planner=False,
                requires_internal_retrieval=False,
            ),
            IntentFallback.NONE,
            None,
            1,
            "router-test",
        )

    async def fail_plan(_state):
        raise AssertionError("case profile questions must not run fact planner")

    monkeypatch.setattr("src.agents.case_graph.route_turn", fake_intent)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", fail_plan)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    state = await build_case_graph(search).ainvoke(
        {
            "semantic": True,
            "text": "latest user turn asks about current case profile",
            "stored": {},
            "case_code": "CASE-001",
            "employee_name": "Nguyễn Văn A",
            "employee_code": "E001",
        }
    )
    assert "Nguyễn Văn A" in state["question"]
    assert "E001" in state["question"]
    assert state.get("handoff") is None


@pytest.mark.asyncio
async def test_graph_case_question_answers_from_description(monkeypatch):
    async def search(_query: SearchQuery):
        raise AssertionError("case memory questions must not retrieve")

    async def fake_intent(_state):
        return IntentResult(
            IntentDecision(
                route=Route.CASE_QA,
                intent_label="ask_case_violation",
                target=IntentTarget.CASE_FACTS,
                confidence=0.93,
            ),
            IntentFallback.NONE,
            None,
            1,
            "router-test",
        )

    async def fail_plan(_state):
        raise AssertionError("case memory questions must not run fact planner")

    monkeypatch.setattr("src.agents.case_graph.route_turn", fake_intent)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", fail_plan)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    state = await build_case_graph(search).ainvoke(
        {
            "semantic": True,
            "text": "nhân viên này vi phạm gì",
            "stored": {},
            "case_code": "CASE30",
            "employee_name": "nGUYỄN Văn K",
            "employee_code": "EMP-09",
            "description": "Phòng ban: ENGINEER\nChức danh: SE\nVi phạm: tự ý nhận hoa hồng của khách",
        }
    )
    assert "Mô tả" in state["question"]
    assert "tự ý nhận hoa hồng của khách" in state["question"]
    assert state.get("handoff") is None


@pytest.mark.asyncio
async def test_graph_routes_policy_question_to_action(monkeypatch):
    seen = {"calls": 0}

    async def search(_query: SearchQuery):
        seen["calls"] += 1
        return []

    async def fake_intent(_state):
        return IntentResult(
            IntentDecision(
                route=Route.POLICY_QA,
                intent_label="ask_internal_policy",
                target=IntentTarget.INTERNAL_POLICY,
                confidence=0.9,
                requires_fact_planner=False,
                requires_internal_retrieval=True,
                requested_action="answer_policy_question",
            ),
            IntentFallback.NONE,
            None,
            1,
            "router-test",
        )

    async def fail_plan(_state):
        raise AssertionError("policy questions must not run fact planner first")

    async def fake_policy_answer(_question, _hits, description=""):
        return "policy answer"

    monkeypatch.setattr("src.agents.case_graph.route_turn", fake_intent)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", fail_plan)
    monkeypatch.setattr("src.agents.case_graph.answer_policy_question", fake_policy_answer)
    state = await build_case_graph(search).ainvoke(
        {
            "semantic": True,
            "text": "hỏi quy định xử lý theo nội quy",
            "stored": _ABSENCE_STORED,
            "description": "nghỉ không phép",
            "incident_date": date(2026, 3, 1),
            "agent_run_id": uuid4(),
            "employee_name": "An",
        }
    )
    assert seen["calls"] == 1
    assert state["requested_action"] == "answer_policy_question"
    assert state["question"] == "policy answer"


@pytest.mark.asyncio
async def test_graph_does_not_extract_after_semantic_router_failure(monkeypatch):
    async def search(_query: SearchQuery):
        raise AssertionError("unclear turns must not retrieve")

    async def fake_intent(_state):
        return IntentResult(
            IntentDecision(
                route=Route.CLARIFY,
                intent_label="unroutable_intent",
                confidence=0,
                reason="invalid route from model",
            ),
            IntentFallback.SEMANTIC,
            "invalid route from model",
            1,
            "router-test",
        )

    async def fail_plan(_state):
        raise AssertionError("semantic router failures must not run fact planner")

    monkeypatch.setattr("src.agents.case_graph.route_turn", fake_intent)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", fail_plan)
    state = await build_case_graph(search).ainvoke(
        {
            "semantic": True,
            "text": "một intent lạ chưa biết xử lý",
            "stored": {},
            "case_code": "CASE-001",
        }
    )
    assert "chưa chắc" in state["question"]
    assert state.get("handoff") is None


@pytest.mark.asyncio
async def test_graph_external_research_requires_disclaimer_and_no_extract(monkeypatch):
    async def search(_query: SearchQuery):
        raise AssertionError("external research must not use internal retrieval")

    seen = {"calls": 0}

    async def fake_external(query: ExternalResearchQuery):
        seen["calls"] += 1
        assert "bị kiện" in query.question
        return ExternalResearchResult(
            query=query.question,
            provider="mcp_http",
            sources=[
                ExternalSource(
                    title="Nguồn external mẫu",
                    url="https://molisa.gov.vn/example",
                    snippet="Doanh nghiệp cần chuẩn bị hồ sơ, chứng cứ và quy trình làm việc liên quan.",
                )
            ],
        )

    async def fake_intent(_state):
        return IntentResult(
            IntentDecision(
                route=Route.EXTERNAL_RESEARCH,
                intent_label="research_public_litigation_guidance",
                confidence=0.86,
                requires_external_research=True,
            ),
            IntentFallback.NONE,
            None,
            1,
            "router-test",
        )

    async def fail_plan(_state):
        raise AssertionError("external research turns must not run fact planner")

    monkeypatch.setattr("src.agents.case_graph.route_turn", fake_intent)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", fail_plan)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    state = await build_case_graph(search, external_research=fake_external).ainvoke(
        {
            "semantic": True,
            "text": "nếu bị kiện thì công ty cần chuẩn bị gì theo thông tin mới nhất?",
            "stored": {},
            "case_code": "CASE-001",
        }
    )
    assert seen["calls"] == 1
    assert state["requested_action"] == "external_research"
    assert "Nguồn external mẫu" in state["question"]
    assert EXTERNAL_RESEARCH_DISCLAIMER in state["question"]
    assert state.get("handoff") is None


@pytest.mark.asyncio
async def test_graph_unsupported_action_does_not_enter_workflow_or_extract(monkeypatch):
    async def search(_query: SearchQuery):
        raise AssertionError("unsupported actions must not retrieve")

    async def fake_intent(_state):
        return IntentResult(
            IntentDecision(
                route=Route.UNSUPPORTED,
                intent_label="approve_and_close_case",
                confidence=0.95,
                requested_action="unsupported",
            ),
            IntentFallback.NONE,
            None,
            1,
            "router-test",
        )

    async def fail_plan(_state):
        raise AssertionError("unsupported actions must not run fact planner")

    monkeypatch.setattr("src.agents.case_graph.route_turn", fake_intent)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", fail_plan)
    state = await build_case_graph(search).ainvoke(
        {
            "semantic": True,
            "text": "duyệt và đóng hồ sơ luôn",
            "stored": {},
            "case_code": "CASE-001",
        }
    )
    assert state["requested_action"] == "unsupported"
    assert "không thể thực hiện" in state["question"]
    assert state.get("handoff") is None


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
