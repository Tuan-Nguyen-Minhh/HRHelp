"""Dispatch reads only the proposal feature 6 just stored."""

from datetime import date
from uuid import uuid4

import pytest

from src.agents.handoff import CaseHandoff, CitedPassage
from src.features.answer.model.agent import build_recommend_agent
from src.features.answer.model.assessment import (
    Assessment,
    CaseSummary,
    DownstreamHandoff,
    EvidenceRef,
    RiskAssessment,
    SanctionAssessment,
)
from src.features.answer.model.dispatch import build_dispatch_agent, hold_code
from src.features.answer.model.layers import BasisLayer
from src.features.answer.model.proposal import ProposalHandoff, close_proposal
from src.features.answer.model.release import DispatchError, save_submission
from src.features.answer.model.standard import applied_standard
from src.features.answer.model.synthesis import guard, unavailable_assessment
from src.features.answer.schema import AnswerView, CitationView, ProcessStep
from src.features.cite.model.passage import Passage
from src.features.clarify.model.catalog import ABSENCE
from src.models.cases import Case
from src.models.recommendations import Recommendation

_READY = {
    "contract_type": "xác định thời hạn",
    "absence_days": "5 ngày trong 30 ngày",
    "notice_form": "không báo",
    "minutes_made": "true",
    "explanation_requested": "true",
}


def _steps(*, minutes: bool = True, explanation: bool = True) -> list[ProcessStep]:
    return [
        ProcessStep(code="MINUTES", label="Lập biên bản vi phạm", done=minutes),
        ProcessStep(code="EXPLANATION_REQUEST", label="Gửi yêu cầu giải trình", done=explanation),
        ProcessStep(code="TIME_LIMIT", label="Kiểm tra thời hiệu xử lý kỷ luật", done=False),
        ProcessStep(code="SIGNER", label="Người có thẩm quyền ban hành quyết định", done=False),
    ]


def _citation(policy_type: str, code: str, layer: BasisLayer) -> CitationView:
    return CitationView(
        citation_id=uuid4(),
        chunk_id=uuid4(),
        layer=layer,
        policy_type=policy_type,
        policy_code=code,
        policy_name=code,
        quote="Nội dung điều khoản.",
        article="125",
        clause="1",
        point=None,
        score=0.5,
    )


def _proposal(**changes) -> ProposalHandoff:
    base = {
        "recommendation_id": uuid4(),
        "case_id": uuid4(),
        "agent_run_id": uuid4(),
        "incident_date": date(2026, 3, 1),
        "employee_name": "An",
        "family": ABSENCE,
        "facts": dict(_READY),
        "fact_lines": ["Loại hợp đồng: xác định thời hạn"],
        "rationale": "Đủ căn cứ.",
        "sanction_type": "DISMISSAL",
        "process_steps": _steps(),
        "risk_level": "MEDIUM",
        "missing_internal_rule": False,
        "message": "Đề xuất.",
        "legal_basis": [_citation("LAW", "BLLD", BasisLayer.LEGAL_BASIS)],
        "internal_rule": [_citation("INTERNAL_RULE", "NQ", BasisLayer.INTERNAL_RULE)],
        "precedent": [],
        "inspection_risk": [],
    }
    base.update(changes)
    return ProposalHandoff(**base)


def _passage(policy_type: str, code: str, content: str) -> Passage:
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
        policy_name=code,
    )


class _Session:
    def __init__(self, recommendation: Recommendation):
        self.recommendation = recommendation
        self.added = []

    def add(self, row) -> None:
        self.added.append(row)

    async def get(self, model, key):
        assert model is Recommendation
        assert key == self.recommendation.id
        return self.recommendation

    async def flush(self) -> None:
        return None


def test_hold_code_follows_the_first_matching_rule():
    assert hold_code(_proposal(sanction_type="TERMINATION", risk_level="HIGH")) == "TERMINATION"
    assert hold_code(_proposal(sanction_type=None, risk_level="HIGH")) == "OPEN_SANCTION"
    assert hold_code(_proposal(risk_level="CRITICAL")) == "RISK_HIGH"
    assert hold_code(_proposal(missing_internal_rule=True)) == "MISSING_INTERNAL_RULE"
    assert hold_code(_proposal(process_steps=_steps(minutes=False))) == "PROCEDURE_OPEN"
    assert hold_code(_proposal()) is None


@pytest.mark.asyncio
async def test_dispatch_holds_without_drafts():
    state = await build_dispatch_agent().ainvoke({"proposal": _proposal(sanction_type=None, rationale="Chưa chốt mức.")})
    result = state["result"]
    assert result.disposition == "HOLD"
    assert result.hold_code == "OPEN_SANCTION"
    assert result.drafts == ()
    assert result.reason == "Chưa chốt mức."


@pytest.mark.asyncio
async def test_dispatch_submits_four_drafts_and_copies_the_sanction():
    state = await build_dispatch_agent().ainvoke({"proposal": _proposal(employee_name=None)})
    result = state["result"]
    assert result.disposition == "SUBMIT"
    assert result.hold_code is None
    assert [item.draft_type for item in result.drafts] == [
        "MINUTES",
        "EXPLANATION_REQUEST",
        "DECISION",
        "TICKET",
    ]
    decision = result.drafts[2].content
    ticket = result.drafts[3]
    assert "sa thải (DISMISSAL)" in decision
    assert "Bản thảo. Chưa có mã quyết định. Chưa có người ký." in decision
    assert "Nội dung điều khoản." in ticket.content
    assert ticket.title == "Phiếu chuyển pháp chế"
    assert "TERMINATION" not in ticket.content


@pytest.mark.asyncio
async def test_dispatch_rejects_a_message_that_is_not_a_proposal():
    with pytest.raises(TypeError):
        await build_dispatch_agent().ainvoke({"proposal": {"sanction_type": "WARNING"}})


@pytest.mark.asyncio
async def test_open_sanction_from_feature_6_is_held():
    handoff = _handoff([_passage("LAW", "BLLD", "Kỷ luật lao động sa thải.")])
    state = await build_recommend_agent().ainvoke({"handoff": handoff})
    proposal = close_proposal(handoff, _view(handoff, state))
    result = (await build_dispatch_agent().ainvoke({"proposal": proposal}))["result"]
    assert state["draft"].decision.sanction_type is None
    assert proposal.standard is not None
    assert proposal.standard.aligned is False
    assert proposal.standard.sanction_type is None
    assert result.disposition == "HOLD"
    assert result.hold_code == "OPEN_SANCTION"


_ART_125 = (
    "Hình thức xử lý kỷ luật sa thải được người sử dụng lao động áp dụng trong trường hợp sau đây:\n"
    "4. Người lao động tự ý bỏ việc 05 ngày cộng dồn trong thời hạn 30 ngày "
    "hoặc 20 ngày cộng dồn trong thời hạn 365 ngày mà không có lý do chính đáng."
)


@pytest.mark.asyncio
async def test_company_level_above_the_retrieved_ceiling_is_held(monkeypatch):
    async def ungrounded(message, _layered):
        return unavailable_assessment(message.facts, "Fact chỉ có đi muộn, đoạn nội quy không chứng minh được mức.")

    monkeypatch.setattr("src.features.answer.model.agent.synthesize", ungrounded)
    handoff = _handoff(
        [
            _passage("LAW", "BLLD", "1. Khiển trách.\n2. Kéo dài thời hạn nâng lương không quá 06 tháng.\n3. Cách chức."),
            _passage("INTERNAL_RULE", "NQ", "Đi muộn lần đầu thì cách chức."),
            _passage("DECREE", "145/2020/ND-CP", "Đi muộn lần đầu thì chỉ được khiển trách."),
        ],
        description="đi muộn lần đầu",
    )
    state = await build_recommend_agent().ainvoke({"handoff": handoff})
    proposal = close_proposal(handoff, _view(handoff, state))
    result = (await build_dispatch_agent().ainvoke({"proposal": proposal}))["result"]
    assert state["draft"].decision.sanction_type is None
    assert result.disposition == "HOLD"
    assert result.hold_code == "OPEN_SANCTION"


@pytest.mark.asyncio
async def test_locked_dismissal_from_feature_6_is_submitted(monkeypatch):
    async def grounded(_message, layered):
        law = layered.legal_basis[0]
        rule = layered.internal_rule[0]
        raw = Assessment(
            case_summary=CaseSummary(violation="nghỉ không phép", facts=dict(_READY)),
            sanction_assessment=SanctionAssessment(
                status="SUPPORTED",
                recommended_sanction="DISMISSAL",
                reason="Đoạn luật và nội quy đã lấy nêu sa thải.",
                evidence=[
                    EvidenceRef(chunk_id=str(law.chunk_id), quote="05 ngày cộng dồn trong thời hạn 30 ngày"),
                    EvidenceRef(chunk_id=str(rule.chunk_id), quote=rule.content),
                ],
            ),
            risk_assessment=RiskAssessment(level="LOW", reasons=["Đủ trích dẫn."]),
            downstream_handoff=DownstreamHandoff(can_recommend=True),
        )
        return guard(raw, [law, rule])

    monkeypatch.setattr("src.features.answer.model.agent.synthesize", grounded)
    handoff = _handoff(
        [
            _passage("LAW", "BLLD", _ART_125),
            _passage("INTERNAL_RULE", "NQ", "Người lao động tự ý bỏ việc không phép thì bị sa thải."),
        ],
        description="nghỉ không phép tự ý bỏ việc",
    )
    state = await build_recommend_agent().ainvoke({"handoff": handoff})
    proposal = close_proposal(handoff, _view(handoff, state))
    result = (await build_dispatch_agent().ainvoke({"proposal": proposal}))["result"]
    assert state["draft"].decision.sanction_type == "DISMISSAL"
    assert proposal.standard is not None
    assert proposal.standard.aligned is True
    assert proposal.standard.sanction_type == "DISMISSAL"
    assert [item.effect for item in proposal.standard.layers] == ["basis", "level", "compare", "excluded"]
    assert result.disposition == "SUBMIT"
    assert result.drafts[3].title == "Phiếu chuyển pháp chế — An"


@pytest.mark.asyncio
async def test_save_submission_moves_the_case_and_writes_the_ticket():
    proposal = _proposal()
    state = await build_dispatch_agent().ainvoke({"proposal": proposal})
    case = Case(
        id=proposal.case_id,
        case_code="C-1",
        created_by=uuid4(),
        status="ANALYZED",
        incident_date=proposal.incident_date,
    )
    recommendation = Recommendation(
        id=proposal.recommendation_id,
        case_id=case.id,
        recommendation="Đề xuất.",
        status="DRAFT",
    )
    session = _Session(recommendation)
    await save_submission(session, case, proposal, state["result"])
    assert case.status == "PENDING_LEGAL"
    assert recommendation.status == "PENDING_REVIEW"
    assert [row.draft_type for row in session.added] == [
        "MINUTES",
        "EXPLANATION_REQUEST",
        "DECISION",
        "TICKET",
    ]
    assert all(row.status == "PENDING_REVIEW" for row in session.added)
    assert all(row.created_by == case.created_by for row in session.added)
    assert all(row.recommendation_id == proposal.recommendation_id for row in session.added)


@pytest.mark.asyncio
async def test_save_submission_rejects_a_short_draft_list_without_writing():
    proposal = _proposal()
    state = await build_dispatch_agent().ainvoke({"proposal": proposal})
    result = state["result"]
    broken = type(result)(result.disposition, result.hold_code, result.reason, result.drafts[:3])
    case = Case(id=proposal.case_id, case_code="C-2", created_by=uuid4(), status="ANALYZED")
    recommendation = Recommendation(
        id=proposal.recommendation_id,
        case_id=case.id,
        recommendation="Đề xuất.",
        status="DRAFT",
    )
    session = _Session(recommendation)
    with pytest.raises(DispatchError):
        await save_submission(session, case, proposal, broken)
    assert session.added == []
    assert case.status == "ANALYZED"
    assert recommendation.status == "DRAFT"


def _handoff(passages: list[Passage], description: str = "") -> CaseHandoff:
    cited = [
        CitedPassage(
            chunk_id=item.chunk_id,
            policy_version_id=item.policy_version_id,
            content=item.content,
            article=item.article,
            clause=item.clause,
            point=item.point,
            score=item.score,
            policy_type=item.policy_type,
            policy_code=item.policy_code,
            policy_name=item.policy_name,
        )
        for item in passages
    ]
    return CaseHandoff(
        incident_date=date(2026, 3, 1),
        employee_name="An",
        description=description,
        family=ABSENCE,
        facts=dict(_READY),
        fact_lines=["Loại hợp đồng: xác định thời hạn"],
        passages=cited,
        missing_internal_rule=not any(item.policy_type == "INTERNAL_RULE" for item in passages),
        agent_run_id=uuid4(),
    )


def _view(handoff: CaseHandoff, state: dict) -> AnswerView:
    draft = state["draft"]
    return AnswerView(
        recommendation_id=uuid4(),
        case_id=uuid4(),
        case_status="ANALYZED",
        agent_run_id=handoff.agent_run_id,
        rationale=draft.decision.rationale,
        sanction_type=draft.decision.sanction_type,
        process_steps=draft.decision.process_steps,
        risk_level=draft.decision.risk_level,
        missing_internal_rule=draft.decision.missing_internal_rule,
        message=draft.prose,
        legal_basis=[],
        internal_rule=[],
        precedent=[],
        inspection_risk=[],
        standard=applied_standard(
            draft.decision.sanction_type,
            draft.decision.risk_level,
            draft.decision.process_steps,
        ),
    )
