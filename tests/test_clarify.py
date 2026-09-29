from uuid import uuid4

import pytest

from src.agents.case_graph import build_case_graph
from src.features.cite.model.query import SearchQuery
from src.features.clarify.model.assess import StoredFact, assess
from src.features.clarify.model.catalog import ABSENCE, GENERAL
from src.features.clarify.model.extract import extract_facts

_ABSENCE_TEXT = (
    "Nhân viên hợp đồng xác định thời hạn nghỉ không phép 5 ngày trong 30 ngày, không báo. "
    "Đã lập biên bản. Chưa gửi yêu cầu giải trình."
)


def test_extracts_absence_facts_and_does_not_treat_a_missing_minutes_as_done():
    found = extract_facts(ABSENCE, _ABSENCE_TEXT)
    assert found["contract_type"] == "xác định thời hạn"
    assert "5" in found["absence_days"]
    assert "30" in found["absence_days"]
    assert found["notice_form"] == "không báo"
    assert found["minutes_made"] == "true"
    assert found["explanation_requested"] == "false"


def test_negative_minutes_win_over_the_word_bien_ban():
    found = extract_facts(ABSENCE, "Nghỉ không phép. Chưa lập biên bản vi phạm.")
    assert found["minutes_made"] == "false"


def test_confirmed_fact_is_not_overwritten_by_a_later_sentence():
    stored = {"contract_type": StoredFact("thử việc", True)}
    plan = assess("Hợp đồng xác định thời hạn, nghỉ không phép.", stored)
    assert plan.merged["contract_type"].value == "thử việc"
    assert plan.merged["contract_type"].confirmed is True


def _chat_graph():
    async def search(_query: SearchQuery):
        raise AssertionError("a chat turn must not cite")

    return build_case_graph(search)


@pytest.mark.asyncio
async def test_open_step_does_not_clarify_or_cite():
    seen: dict[str, str] = {}

    async def opener(state: dict) -> dict:
        seen["code"] = state["case_code"]
        return {"case_id": uuid4(), "conversation_id": uuid4(), "status": "OPEN"}

    async def search(_query: SearchQuery):
        raise AssertionError("opening a case must not cite")

    state = await build_case_graph(search, opener).ainvoke({"step": "open", "case_code": "HS-1"})
    assert seen["code"] == "HS-1"
    assert state["status"] == "OPEN"
    assert state.get("handoff") is None
    assert "question" not in state


@pytest.mark.asyncio
async def test_graph_asks_and_does_not_lock_a_level():
    state = await _chat_graph().ainvoke({"text": "Xin chào", "stored": {}, "advance": False})
    assert state["family"] == GENERAL
    assert state["facts_locked"] is False
    assert "Hợp đồng" in state["question"]
    assert "sanction" not in state["question"].casefold()
    assert "draft" not in state
    assert state.get("handoff") is None


@pytest.mark.asyncio
async def test_graph_stops_when_required_facts_are_confirmed():
    stored = {
        "contract_type": StoredFact("xác định thời hạn", True),
        "violation_summary": StoredFact("đi làm muộn giờ", True),
        "minutes_made": StoredFact("true", True),
        "explanation_requested": StoredFact("true", True),
    }
    state = await _chat_graph().ainvoke({"text": "Xin chào", "stored": stored, "advance": False})
    assert state["facts_locked"] is True
    assert "question" not in state
    assert "draft" not in state
    assert state.get("handoff") is None
