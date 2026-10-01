from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agents.case_graph import build_case_graph
from src.agents.handoff import CaseHandoff, CitedPassage
from src.features.answer.model import answers
from src.features.answer.model.agent import build_recommend_agent
from src.features.answer.model.decide import DecisionInput, decide
from src.features.answer.model.draft import AnswerInput, draft_answer
from src.features.answer.model.layers import LayeredBasis, split_passages
from src.features.answer.model.standard import applied_standard
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


_ART_124 = "1. Khiển trách.\n2. Kéo dài thời hạn nâng lương không quá 06 tháng.\n3. Cách chức.\n4. Sa thải."
_ART_125 = (
    "Hình thức xử lý kỷ luật sa thải được người sử dụng lao động áp dụng trong trường hợp sau đây:\n"
    "4. Người lao động tự ý bỏ việc 05 ngày cộng dồn trong thời hạn 30 ngày "
    "hoặc 20 ngày cộng dồn trong thời hạn 365 ngày tính từ ngày đầu tiên tự ý bỏ việc "
    "mà không có lý do chính đáng."
)
_ABSENCE = "nghỉ không phép tự ý bỏ việc"


def _decide(layered: LayeredBasis, facts: dict[str, str] | None = None, description: str = ""):
    return decide(DecisionInput(family=ABSENCE, facts=facts or _READY, layered=layered, description=description))


def test_dismissal_ceiling_is_the_condition_written_in_the_retrieved_law():
    layered = _layered(
        _passage("LAW", "BLLD", "Bộ luật Lao động", _ART_125),
        _passage("INTERNAL_RULE", "NQ", "Nội quy", "Người lao động tự ý bỏ việc không phép thì bị sa thải."),
    )
    assert _decide(layered, description=_ABSENCE).sanction_type == "DISMISSAL"
    assert _decide(layered, {**_READY, "absence_days": "4 ngày trong 30 ngày"}, _ABSENCE).sanction_type is None
    assert _decide(layered, {**_READY, "absence_days": "5 ngày"}, _ABSENCE).sanction_type is None
    assert _decide(layered, {**_READY, "absence_days": "20 ngày trong 365 ngày"}, _ABSENCE).sanction_type == "DISMISSAL"


def test_a_different_retrieved_threshold_replaces_any_fixed_day_count():
    law = (
        "Hình thức xử lý kỷ luật sa thải được áp dụng trong trường hợp sau đây:\n"
        "Người lao động tự ý bỏ việc 03 ngày cộng dồn trong thời hạn 10 ngày."
    )
    layered = _layered(
        _passage("LAW", "BLLD", "Bộ luật Lao động", law),
        _passage("INTERNAL_RULE", "NQ", "Nội quy", "Tự ý bỏ việc không phép thì bị sa thải."),
    )
    description = "tự ý bỏ việc không phép"
    met = _decide(layered, {**_READY, "absence_days": "3 ngày trong 10 ngày"}, description)
    missed = _decide(layered, {**_READY, "absence_days": "3 ngày trong 30 ngày"}, description)
    assert met.sanction_type == "DISMISSAL"
    assert missed.sanction_type is None


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
        _passage("LAW", "BLLD-2019", "Bộ luật Lao động", _ART_125),
        _passage("INTERNAL_RULE", "NQ", "Nội quy", "Người lao động tự ý bỏ việc không phép thì bị sa thải."),
    )
    decision = _decide(layered, description=_ABSENCE)
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
            description=_ABSENCE,
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


def test_conflicting_sources_collapse_to_one_open_standard():
    layered = _layered(
        _passage("LAW", "BLLD-2019", "Bộ luật Lao động", "Có thể khiển trách hoặc cảnh cáo."),
        _passage("INTERNAL_RULE", "NQ", "Nội quy", "Vi phạm thì khiển trách hoặc cảnh cáo."),
        _passage("DECREE", "283/2026/ND-CP", "Nghị định xử phạt", "Phạt tiền và sa thải."),
        _passage("PRECEDENT", "QD-1", "Vụ cũ", "Vụ trước đã sa thải."),
    )
    facts = {**_READY, "absence_days": "1 ngày trong 30 ngày"}
    decision = _decide(layered, facts)
    standard = applied_standard(decision.sanction_type, decision.risk_level, decision.process_steps)
    prose = draft_answer(
        AnswerInput(
            family=ABSENCE,
            facts=facts,
            fact_lines=["Loại hợp đồng: xác định thời hạn"],
            employee_name="An",
            incident_date=date(2026, 3, 1),
            layered=layered,
            precedent_note="Có 1 đoạn tiền lệ. Tiền lệ chỉ để đối chiếu, không tự nâng mức kỷ luật.",
        )
    ).prose
    assert decision.sanction_type is None
    assert standard.aligned is False
    assert standard.sanction_type is None
    assert len(standard.process_steps) == 4
    assert [item.effect for item in standard.layers] == ["basis", "open", "compare", "excluded"]
    assert "Chuẩn áp dụng" in prose
    assert "Nghị định xử phạt không vào mức kỷ luật." in prose
    assert standard.sanction_type != "TERMINATION"


def test_a_single_company_level_can_be_warning():
    layered = _layered(
        _passage("LAW", "BLLD-2019", "Bộ luật Lao động", _ART_124),
        _passage("INTERNAL_RULE", "NQ", "Nội quy", "Đi muộn lần đầu thì khiển trách."),
    )
    facts = {**_READY, "absence_days": "1 ngày trong 30 ngày"}
    assert _decide(layered, facts, "đi muộn lần đầu").sanction_type == "WARNING"
    assert _decide(layered, facts, _ABSENCE).sanction_type is None


def test_a_harsher_rule_drops_to_the_level_the_retrieved_ceiling_still_allows():
    rule = (
        "Nghỉ không phép tự ý bỏ việc dưới 5 ngày thì khiển trách. "
        "Tự ý bỏ việc không phép từ 05 ngày cộng dồn trong thời hạn 30 ngày thì sa thải."
    )
    layered = _layered(
        _passage("LAW", "BLLD", "Bộ luật Lao động", f"{_ART_124}\n{_ART_125}"),
        _passage("INTERNAL_RULE", "NQ", "Nội quy", rule),
    )
    facts = {**_READY, "absence_days": "1 ngày trong 30 ngày"}
    decision = _decide(layered, facts, _ABSENCE)
    assert decision.sanction_type == "WARNING"


def test_two_lawful_levels_stay_open_for_feature_7_to_hold():
    layered = _layered(
        _passage("LAW", "BLLD", "Bộ luật Lao động", _ART_124),
        _passage("INTERNAL_RULE", "NQ", "Nội quy", "Đi muộn lần đầu thì khiển trách hoặc cách chức."),
    )
    decision = _decide(layered, description="đi muộn lần đầu")
    assert decision.sanction_type is None
    assert decision.risk_level == "MEDIUM"


def test_a_guiding_decree_sets_the_ceiling_and_a_penalty_decree_does_not():
    penalty = _passage("DECREE", "283/2026/ND-CP", "Nghị định xử phạt", "Phạt tiền và sa thải.")
    precedent = _passage("PRECEDENT", "QD-1", "Vụ cũ", "Vụ trước đã sa thải.")
    decree = _passage("DECREE", "145/2020/ND-CP", "Nghị định 145", "Đi muộn lần đầu thì chỉ được khiển trách.")
    harsh = _passage("INTERNAL_RULE", "NQ", "Nội quy", "Đi muộn lần đầu thì cách chức.")
    matched = _passage("INTERNAL_RULE", "NQ", "Nội quy", "Đi muộn lần đầu thì khiển trách.")
    blocked = _decide(_layered(decree, harsh, penalty, precedent), description="đi muộn lần đầu")
    kept = _decide(_layered(decree, matched, penalty, precedent), description="đi muộn lần đầu")
    assert blocked.sanction_type is None
    assert "trần" in blocked.rationale
    assert kept.sanction_type == "WARNING"


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
