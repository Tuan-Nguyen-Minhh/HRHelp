"""End-to-end gates around the four agents. Each graph stays behind FastAPI."""

from datetime import date
from uuid import uuid4

import pytest

from src.agents.case_graph import build_case_graph
from src.common.access import require_mutable_case
from src.common.errors import AppError
from src.features.cite.model.query import SearchQuery
from src.features.clarify.model.assess import StoredFact
from src.features.clarify.model.catalog import ABSENCE
from src.features.clarify.model.decision import CaseFamily, ClarifyDecision, ExtractedFact, RequestedAction, UserIntent
from src.features.clarify.model.graph import route_after_extract
from src.features.clarify.model.policy import apply_decision
from src.models.cases import Case
from src.models.users import User

_ABSENCE = {
    "contract_type": StoredFact("không xác định thời hạn", True),
    "absence_days": StoredFact("5 ngày", True),
    "notice_form": StoredFact("không báo", True),
    "minutes_made": StoredFact("true", True),
    "explanation_requested": StoredFact("true", True),
}


def _fact(key: str, value: str, evidence: str) -> ExtractedFact:
    return ExtractedFact(key=key, value=value, confidence=0.95, evidence=evidence, ambiguous=False)


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
        "conflicts": [],
        "requested_action": plan.requested_action,
        "planner_fallback": plan.planner_fallback,
    }
    state.update(extra)
    return state


def test_later_turns_replace_and_complete_without_inventing_facts():
    first = apply_decision(
        "Anh A nghỉ không phép 5 ngày.",
        {},
        _decision(extracted_facts=[_fact("absence_days", "5 ngày", "nghỉ không phép 5 ngày")]),
    )
    assert first.family == ABSENCE
    assert first.merged["absence_days"].confirmed is True
    assert first.locked is False
    assert route_after_extract(_state(first, incident_date=date(2026, 3, 1), agent_run_id=uuid4())) == "ask"

    second = apply_decision(
        "Hợp đồng của anh ấy là không xác định thời hạn. Không báo.",
        first.merged,
        _decision(
            extracted_facts=[
                _fact("contract_type", "không xác định thời hạn", "không xác định thời hạn"),
                _fact("notice_form", "không báo", "Không báo"),
            ]
        ),
    )
    assert second.merged["absence_days"].value == "5 ngày"
    assert second.locked is False

    third = apply_decision(
        "Không phải 5 ngày, là 6 ngày. Đã lập biên bản và đã yêu cầu giải trình.",
        second.merged,
        _decision(
            extracted_facts=[
                _fact("absence_days", "6 ngày", "là 6 ngày"),
                _fact("minutes_made", "true", "Đã lập biên bản"),
                _fact("explanation_requested", "true", "đã yêu cầu giải trình"),
            ]
        ),
    )
    assert third.merged["absence_days"].value == "6 ngày"
    assert third.locked is True
    assert route_after_extract(_state(third)) == "done"
    run_id = uuid4()
    assert route_after_extract(_state(third, incident_date=date(2026, 3, 1), agent_run_id=run_id)) == "retrieve"


@pytest.mark.asyncio
async def test_locked_facts_without_an_incident_date_do_not_retrieve():
    async def search(_query: SearchQuery):
        raise AssertionError("a case without an incident date must not retrieve")

    state = await build_case_graph(search).ainvoke(
        {
            "text": "Nhân viên nghỉ không phép.",
            "stored": _ABSENCE,
            "description": "nghỉ không phép",
            "agent_run_id": uuid4(),
            "employee_name": "An",
        }
    )
    assert state["facts_locked"] is True
    assert state.get("handoff") is None


@pytest.mark.asyncio
async def test_handoff_carries_the_case_id_and_confirmed_facts():
    case_id = uuid4()
    seen: list[SearchQuery] = []

    async def search(query: SearchQuery):
        seen.append(query)
        return []

    state = await build_case_graph(search).ainvoke(
        {
            "step": "cite",
            "text": "Nhân viên nghỉ không phép.",
            "stored": _ABSENCE,
            "description": "nghỉ không phép",
            "incident_date": date(2026, 3, 1),
            "agent_run_id": uuid4(),
            "employee_name": "An",
            "case_id": case_id,
        }
    )
    handoff = state["handoff"]
    assert seen[0].incident_date == date(2026, 3, 1)
    assert handoff.case_id == case_id
    assert handoff.facts["absence_days"] == "5 ngày"
    assert handoff.incident_date == date(2026, 3, 1)
    assert handoff.passages == []
    assert handoff.missing_internal_rule is True


class _Cases:
    def __init__(self, case: Case) -> None:
        self.case = case

    async def get(self, _model, _key):
        return self.case


@pytest.mark.asyncio
async def test_pending_legal_rejects_another_chat_turn():
    actor_id = uuid4()
    case = Case(id=uuid4(), case_code="C-9", created_by=actor_id, status="PENDING_LEGAL")
    actor = User(id=actor_id, email="hr.pipeline@vinuni.edu.vn", password_hash="x", role="HR", is_active=True)
    with pytest.raises(AppError) as caught:
        await require_mutable_case(_Cases(case), case.id, actor)
    assert caught.value.status_code == 409
