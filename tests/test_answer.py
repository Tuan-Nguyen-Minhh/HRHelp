from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agents.case_graph import build_case_graph
from src.agents.handoff import CaseHandoff, CitedPassage
from src.features.answer.model import answers
from src.features.answer.model.agent import build_recommend_agent
from src.features.answer.model.decide import DecisionInput, absence_meets_dismissal, decide
from src.features.answer.model.draft import AnswerInput, draft_answer
from src.features.answer.model.layers import LayeredBasis, split_passages
from src.features.answer.schema.render import HEADINGS
from src.features.cite.model.passage import Passage
from src.features.cite.model.query import SearchQuery
from src.features.clarify.model.assess import StoredFact
from src.features.clarify.model.catalog import ABSENCE
from src.models.cases import Case

_READY = {
    "contract_type": "xác định thời hạn",
    "absence_days": "5 ngày trong 30 ngày",
    "notice_form": "không báo",
    "minutes_made": "true",
    "explanation_requested": "true",
}


def _passage(policy_type: str, code: str, name: str, content: str) -> Passage:
    return Passage(
        chunk_id=uuid4(),
        policy_version_id=uuid4(),
        content=content,
        article="125",
        clause="1",
        point=None,
        score=0.8,
        policy_type=policy_type,
        policy_code=code,
        policy_name=name,
    )


def _layered(*passages: Passage) -> LayeredBasis:
    return split_passages(list(passages))


def _decide(layered: LayeredBasis, facts: dict[str, str] | None = None):
    return decide(DecisionInput(family=ABSENCE, facts=facts or _READY, layered=layered))


def test_window_must_be_stated_before_dismissal_is_considered():
    assert absence_meets_dismissal("5 ngày trong 30 ngày") is True
    assert absence_meets_dismissal("20 ngày trong 365 ngày") is True
    assert absence_meets_dismissal("5 ngày") is False
    assert absence_meets_dismissal("4 ngày trong 30 ngày") is False


def test_no_corpus_does_not_lock_a_sanction():
    decision = _decide(_layered())
    assert decision.sanction_type is None
    assert decision.risk_level == "CRITICAL"


def test_decree_283_alone_cannot_set_a_company_sanction():
    penalty = _passage(
        "DECREE", "283/2026/ND-CP", "Nghị định xử phạt vi phạm hành chính", "Phạt tiền người sử dụng lao động."
    )
    decision = _decide(_layered(penalty))
    assert decision.sanction_type is None
    assert decision.risk_level == "HIGH"
    assert decision.sanction_type != "TERMINATION"


def test_missing_internal_rule_keeps_the_level_open():
    law = _passage("LAW", "BLLD-2019", "Bộ luật Lao động", "Người lao động có thể bị sa thải.")
    decision = _decide(_layered(law))
    assert decision.sanction_type is None
    assert decision.risk_level == "HIGH"
    assert decision.missing_internal_rule is True


def test_internal_rule_without_law_does_not_lock_a_sanction():
    rule = _passage("INTERNAL_RULE", "NQ", "Nội quy", "Nghỉ không phép thì bị sa thải.")
    decision = _decide(_layered(rule))
    assert decision.sanction_type is None
    assert decision.risk_level == "HIGH"


def test_page_index_headings_do_not_lock_a_sanction():
    layered = _layered(
        _passage("LAW", "BLLD-2019", "Bộ luật Lao động", "Sa thải."),
        _passage("INTERNAL_RULE", "NQ", "Nội quy", "Nghỉ không phép thì bị sa thải."),
    )
    decision = decide(DecisionInput(family=ABSENCE, facts=_READY, layered=layered, retrieval="page_index"))
    assert decision.sanction_type is None
    assert decision.risk_level == "HIGH"


def test_incomplete_procedure_blocks_dismissal():
    layered = _layered(
        _passage("LAW", "BLLD-2019", "Bộ luật Lao động", "Sa thải."),
        _passage("INTERNAL_RULE", "NQ", "Nội quy", "Tự ý nghỉ không phép thì bị sa thải."),
    )
    facts = {**_READY, "minutes_made": "false"}
    decision = _decide(layered, facts)
    assert decision.sanction_type is None
    assert decision.risk_level == "HIGH"


def test_dismissal_is_not_termination():
    layered = _layered(
        _passage("LAW", "BLLD-2019", "Bộ luật Lao động", "Sa thải người lao động."),
        _passage("INTERNAL_RULE", "NQ", "Nội quy", "Người lao động tự ý bỏ việc không phép thì bị sa thải."),
    )
    decision = _decide(layered)
    assert decision.sanction_type == "DISMISSAL"
    assert "TERMINATION" in decision.rationale
    prose = draft_answer(
        AnswerInput(
            family=ABSENCE,
            facts=_READY,
            fact_lines=["Loại hợp đồng: xác định thời hạn"],
            employee_name="An",
            incident_date=date(2026, 3, 1),
            layered=layered,
            precedent_note="Không có đoạn tiền lệ trong lượt đối chiếu này.",
        )
    ).prose
    assert "DISMISSAL" in prose
    assert "Không đề xuất chấm dứt hợp đồng (TERMINATION)." in prose
    for heading in HEADINGS:
        assert heading in prose


def test_termination_wording_in_an_internal_rule_is_not_selected():
    layered = _layered(
        _passage("LAW", "BLLD-2019", "Bộ luật Lao động", "Chấm dứt hợp đồng lao động."),
        _passage("INTERNAL_RULE", "NQ", "Nội quy", "Công ty được chấm dứt hợp đồng."),
    )
    facts = {**_READY, "absence_days": "1 ngày trong 30 ngày"}
    decision = _decide(layered, facts)
    assert decision.sanction_type is None


def test_a_single_company_level_can_be_warning():
    layered = _layered(
        _passage("LAW", "BLLD-2019", "Bộ luật Lao động", "Hình thức kỷ luật."),
        _passage("INTERNAL_RULE", "NQ", "Nội quy", "Đi muộn lần đầu thì khiển trách."),
    )
    facts = {**_READY, "absence_days": "1 ngày trong 30 ngày"}
    decision = _decide(layered, facts)
    assert decision.sanction_type == "WARNING"


@pytest.mark.asyncio
async def test_cite_step_returns_a_handoff_and_does_not_draft_a_sanction():
    law = _passage("LAW", "BLLD-2019", "Bộ luật Lao động", "Kỷ luật lao động sa thải.")
    penalty = _passage("DECREE", "283_2026_ND-CP", "Nghị định xử phạt", "Phạt tiền.")

    async def search(_query: SearchQuery) -> list[Passage]:
        return [law, penalty]

    graph = build_case_graph(search)
    stored = {key: StoredFact(value, True) for key, value in _READY.items()}
    state = await graph.ainvoke(
        {
            "text": "Nghỉ không phép",
            "stored": stored,
            "advance": True,
            "incident_date": date(2026, 3, 1),
            "agent_run_id": uuid4(),
            "description": "nghỉ không phép",
            "employee_name": "An",
        }
    )
    assert "draft" not in state
    assert state["handoff"].missing_internal_rule is True
    assert [item.policy_code for item in state["handoff"].passages] == ["BLLD-2019", "283_2026_ND-CP"]


@pytest.mark.asyncio
async def test_recommend_agent_reads_only_the_handoff_message():
    law = _passage("LAW", "BLLD-2019", "Bộ luật Lao động", "Kỷ luật lao động sa thải.")
    penalty = _passage("DECREE", "283_2026_ND-CP", "Nghị định xử phạt", "Phạt tiền.")
    message = CaseHandoff(
        incident_date=date(2026, 3, 1),
        employee_name="An",
        description="nghỉ không phép",
        family=ABSENCE,
        facts=_READY,
        fact_lines=["Loại hợp đồng: xác định thời hạn"],
        passages=[_cited(law), _cited(penalty)],
        missing_internal_rule=True,
        agent_run_id=uuid4(),
        query="nghỉ không phép",
    )
    state = await build_recommend_agent().ainvoke({"handoff": message})
    assert state["draft"].decision.sanction_type is None
    assert state["draft"].decision.risk_level == "HIGH"
    assert state["layered"].inspection_risk[0].policy_code == "283_2026_ND-CP"


@pytest.mark.asyncio
async def test_publish_stores_a_draft_and_citations_from_the_handoff(monkeypatch):
    law = _passage("LAW", "BLLD-2019", "Bộ luật Lao động", "Kỷ luật lao động sa thải.")
    case = Case(id=uuid4(), incident_date=date(2026, 3, 1), status="NEED_INFO")
    handoff = CaseHandoff(
        incident_date=case.incident_date,
        employee_name="An",
        family=ABSENCE,
        facts=_READY,
        passages=[_cited(law)],
        missing_internal_rule=True,
        agent_run_id=uuid4(),
    )
    supersede = AsyncMock()
    insert_recommendation = AsyncMock(side_effect=lambda _session, row: row)
    insert_citations = AsyncMock(return_value=[SimpleNamespace(id=uuid4())])
    monkeypatch.setattr(answers, "supersede_drafts", supersede)
    monkeypatch.setattr(answers, "ensure_violation", AsyncMock(return_value=False))
    monkeypatch.setattr(answers, "insert_recommendation", insert_recommendation)
    monkeypatch.setattr(answers, "insert_citations", insert_citations)

    view = await answers.publish(object(), answers.PublishWork(case, handoff, uuid4()))

    row = insert_recommendation.await_args.args[1]
    citation = insert_citations.await_args.args[2][0]
    assert row.status == "DRAFT"
    assert row.sanction_type is None
    assert row.risk_level == "HIGH"
    assert row.agent_run_id == view.agent_run_id
    assert citation.chunk_id == law.chunk_id
    assert citation.quote == law.content
    assert case.status == "ANALYZED"
    assert view.legal_basis[0].chunk_id == law.chunk_id
    supersede.assert_awaited_once()


def _cited(passage: Passage) -> CitedPassage:
    return CitedPassage(
        chunk_id=passage.chunk_id,
        policy_version_id=passage.policy_version_id,
        content=passage.content,
        article=passage.article,
        clause=passage.clause,
        point=passage.point,
        score=passage.score,
        policy_type=passage.policy_type,
        policy_code=passage.policy_code,
        policy_name=passage.policy_name,
    )
