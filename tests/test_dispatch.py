"""Dispatch reads only the proposal feature 6 just stored."""

import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.agents.handoff import CaseHandoff, CitedPassage
from src.common.clock import utc_now
from src.common.errors import AppError
from src.features.answer.model.agent import build_recommend_agent
from src.features.answer.model.assessment import (
    Assessment,
    CaseSummary,
    DownstreamHandoff,
    EvidenceRef,
    RiskAssessment,
    SanctionAssessment,
)
from src.features.answer.model.dispatch import build_dispatch_agent, hold_code, ready_to_dispatch
from src.features.answer.model.layers import BasisLayer
from src.features.answer.model.proposal import ProposalHandoff, close_proposal
from src.features.answer.model.release import DispatchError, save_submission
from src.features.answer.model.send import ask_to_send, send_ticket, with_preview
from src.features.answer.model.standard import applied_standard
from src.features.answer.model.synthesis import guard, unavailable_assessment
from src.features.answer.schema import AnswerView, CitationView, DraftView, ProcessStep, SendTicketRequest
from src.features.answer.schema.present import with_packet
from src.features.cite.model.passage import Passage
from src.features.clarify.model.catalog import ABSENCE
from src.models.agent_runs import AgentRun
from src.models.case_drafts import CaseDraft
from src.models.cases import Case
from src.models.messages import Message
from src.models.recommendations import Recommendation
from src.models.users import User

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


class _Nested:
    def __init__(self, session: "_Boom") -> None:
        self.session = session

    async def __aenter__(self) -> "_Nested":
        self.added = list(self.session.added)
        self.case_status = self.session.case.status
        self.recommendation_status = self.session.recommendation.status
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            self.session.added = self.added
            self.session.case.status = self.case_status
            self.session.recommendation.status = self.recommendation_status
        return False


class _Boom(_Session):
    def __init__(self, recommendation: Recommendation, case: Case) -> None:
        super().__init__(recommendation)
        self.case = case

    def begin_nested(self) -> _Nested:
        return _Nested(self)

    async def flush(self) -> None:
        raise RuntimeError("flush failed")


def test_packet_reports_the_hold_or_the_legal_ticket():
    held = with_packet(_packet_view(sanction_type=None, risk_level="HIGH"), [])
    assert held.ticket is not None
    assert held.ticket.disposition == "HOLD"
    assert held.ticket.hold_code == "OPEN_SANCTION"
    assert held.ticket.queue == "HELD"
    assert held.drafts == []
    assert held.sanction_type is None

    ready = with_packet(_packet_view(), [])
    assert ready.ticket is not None
    assert ready.ticket.disposition == "NOT_SENT"
    assert ready.drafts == []

    ticket = DraftView(
        draft_id=uuid4(),
        draft_type="TICKET",
        title="Phiếu chuyển pháp chế",
        content="Nội dung phiếu",
        status="PENDING_REVIEW",
    )
    sent = with_packet(_packet_view(case_status="PENDING_LEGAL"), [ticket])
    assert sent.ticket is not None
    assert sent.ticket.disposition == "SUBMIT"
    assert sent.ticket.queue == "PENDING_LEGAL"
    assert sent.drafts[0].content == "Nội dung phiếu"
    assert sent.sanction_type == "DISMISSAL"

    preview = DraftView(
        draft_id=uuid4(),
        draft_type="TICKET",
        title="Phiếu chuyển pháp chế",
        content="Nội dung phiếu",
        status="PREVIEW",
    )
    waiting = with_packet(_packet_view(), [preview])
    assert waiting.ticket is not None
    assert waiting.ticket.disposition == "PREVIEW"
    assert waiting.ticket.queue == "READY"
    assert waiting.ticket.hold_code is None


def _packet_view(**changes) -> AnswerView:
    steps = changes.pop("process_steps", _steps())
    sanction = changes.pop("sanction_type", "DISMISSAL")
    risk = changes.pop("risk_level", "LOW")
    missing = changes.pop("missing_internal_rule", False)
    fields = {
        "recommendation_id": uuid4(),
        "case_id": uuid4(),
        "case_status": "ANALYZED",
        "agent_run_id": uuid4(),
        "rationale": "Đủ căn cứ.",
        "sanction_type": sanction,
        "process_steps": steps,
        "risk_level": risk,
        "missing_internal_rule": missing,
        "message": "Chuẩn áp dụng\nMột chuẩn.\n\nNhận định\nĐủ căn cứ.",
        "legal_basis": [],
        "internal_rule": [],
        "precedent": [],
        "inspection_risk": [],
        "standard": applied_standard(sanction if sanction != "TERMINATION" else None, risk, steps),
    }
    fields.update(changes)
    return AnswerView(**fields)


def test_dispatch_runs_only_for_a_draft_on_an_analyzed_case():
    assert ready_to_dispatch("ANALYZED", "DRAFT") is True
    assert ready_to_dispatch("ANALYZED", "PENDING_REVIEW") is False
    assert ready_to_dispatch("ANALYZED", "SUPERSEDED") is False
    assert ready_to_dispatch("ANALYZED", "REJECTED") is False
    assert ready_to_dispatch("PENDING_LEGAL", "DRAFT") is False
    assert ready_to_dispatch("NEED_INFO", "DRAFT") is False


def test_hold_code_follows_the_first_matching_rule():
    assert hold_code(_proposal(sanction_type="TERMINATION", risk_level="HIGH")) == "TERMINATION"
    assert hold_code(_proposal(sanction_type=None, risk_level="HIGH")) == "OPEN_SANCTION"
    assert hold_code(_proposal(risk_level="CRITICAL")) == "RISK_HIGH"
    assert hold_code(_proposal(missing_internal_rule=True)) == "MISSING_INTERNAL_RULE"
    assert hold_code(_proposal(process_steps=_steps(minutes=False))) == "PROCEDURE_OPEN"
    assert hold_code(_proposal()) is None


@pytest.mark.asyncio
async def test_dispatch_hold_still_returns_the_review_minutes():
    state = await build_dispatch_agent().ainvoke({"proposal": _proposal(sanction_type=None, rationale="Chưa ghi một mức.")})
    result = state["result"]
    assert result.disposition == "HOLD"
    assert result.hold_code == "OPEN_SANCTION"
    assert [item.draft_type for item in result.drafts] == ["MINUTES"]
    assert "Kết quả đánh giá" in result.drafts[0].content
    assert "Chưa ghi một mức." in result.drafts[0].content
    assert result.reason == "Chưa ghi một mức."


@pytest.mark.asyncio
async def test_review_minutes_use_the_case_report_when_feature_6_wrote_one():
    report = "BIÊN BẢN ĐÁNH GIÁ VỤ VIỆC\n\nI. THÔNG TIN VỤ VIỆC\nNhân viên: An"
    state = await build_dispatch_agent().ainvoke(
        {"proposal": _proposal(sanction_type=None, message=report, rationale="Theo nội quy.")}
    )
    result = state["result"]
    assert result.drafts[0].content == report
    assert result.hold_code == "OPEN_SANCTION"


@pytest.mark.asyncio
async def test_dispatch_submits_four_drafts_and_copies_the_sanction():
    state = await build_dispatch_agent().ainvoke(
        {"proposal": _proposal(employee_name=None, employee_code="EMP-001")}
    )
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
    body = json.loads(ticket.content)
    assert body["employee"] == {"name": None, "code": "EMP-001"}
    assert body["case"]["incident_date"] == "2026-03-01"
    assert body["case"]["family"] == "UNAUTHORIZED_ABSENCE"
    assert body["facts"]["absence_days"] == "5 ngày trong 30 ngày"
    assert body["violation"]["sanction_type"] == "DISMISSAL"
    assert body["violation"]["summary"] == "Đủ căn cứ."
    assert body["risk"] == "MEDIUM"
    assert [step["code"] for step in body["process_steps"]] == [
        "MINUTES",
        "EXPLANATION_REQUEST",
        "TIME_LIMIT",
        "SIGNER",
    ]
    assert body["citations"][0]["quote"] == "Nội dung điều khoản."
    assert body["citations"][0]["chunk_id"]
    assert body["legal"] == {"code": None}
    named = await build_dispatch_agent().ainvoke(
        {"proposal": _proposal(employee_code="EMP-001", legal_code="PC-014")}
    )
    named_body = json.loads(named["result"].drafts[3].content)
    assert named_body["legal"] == {"code": "PC-014"}
    assert named_body["employee"]["code"] == "EMP-001"


@pytest.mark.asyncio
async def test_dispatch_rejects_a_message_that_is_not_a_proposal():
    with pytest.raises(TypeError):
        await build_dispatch_agent().ainvoke({"proposal": {"sanction_type": "WARNING"}})


@pytest.mark.asyncio
async def test_open_sanction_from_feature_6_is_held(monkeypatch):
    async def offline(message, _layered):
        return unavailable_assessment(message.facts, "offline")

    monkeypatch.setattr("src.features.answer.model.agent.synthesize", offline)
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


@pytest.mark.asyncio
async def test_save_submission_does_not_dispatch_the_same_recommendation_twice():
    proposal = _proposal()
    state = await build_dispatch_agent().ainvoke({"proposal": proposal})
    case = Case(
        id=proposal.case_id,
        case_code="C-3",
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
    with pytest.raises(DispatchError):
        await save_submission(session, case, proposal, state["result"])
    assert len(session.added) == 4
    assert case.status == "PENDING_LEGAL"
    assert recommendation.status == "PENDING_REVIEW"


@pytest.mark.asyncio
async def test_save_submission_flush_failure_keeps_the_draft():
    proposal = _proposal()
    state = await build_dispatch_agent().ainvoke({"proposal": proposal})
    case = Case(
        id=proposal.case_id,
        case_code="C-4",
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
    session = _Boom(recommendation, case)
    with pytest.raises(RuntimeError, match="flush failed"):
        await save_submission(session, case, proposal, state["result"])
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


def test_send_ticket_request_rejects_a_blank_legal_code():
    with pytest.raises(ValidationError):
        SendTicketRequest(legal_code="   ")
    with pytest.raises(ValidationError):
        SendTicketRequest(legal_code="PC-014")
    assert SendTicketRequest(legal_code="  Legal.Demo@Vinuni.edu.vn ").legal_code == "legal.demo@vinuni.edu.vn"


class _Fact:
    def __init__(self, key: str, value: str, confirmed: bool = True) -> None:
        self.fact_key = key
        self.fact_value = value
        self.confirmed = confirmed


class _SendSession:
    def __init__(self, case: Case, recommendation: Recommendation) -> None:
        self.case = case
        self.recommendation = recommendation
        self.added: list[object] = []
        self.committed = 0

    def add(self, row: object) -> None:
        self.added.append(row)

    async def get(self, model, key):
        if model is Case and key == self.case.id:
            return self.case
        if model is Recommendation and key == self.recommendation.id:
            return self.recommendation
        return None

    async def flush(self) -> None:
        return None

    async def execute(self, stmt):
        case = self.case

        class _Locked:
            def scalar_one_or_none(self):
                return case

        return _Locked()

    async def scalars(self, stmt):
        class _Rows:
            def all(self):
                return []

        return _Rows()

    async def commit(self) -> None:
        self.committed += 1


@pytest.mark.asyncio
async def test_preview_shows_the_ticket_before_anything_is_stored(monkeypatch):
    case = Case(
        id=uuid4(),
        case_code="C-PREVIEW",
        created_by=uuid4(),
        status="ANALYZED",
        incident_date=date(2026, 3, 1),
        employee_name="An",
        employee_code="NV-1",
        description="Nghỉ không phép",
    )

    async def rows(session, case_id):
        return [_Fact("absence_days", "5 ngày trong 30 ngày"), _Fact("notice_form", "không báo")]

    monkeypatch.setattr("src.features.answer.model.send.list_fact_rows", rows)
    shown = await with_preview(None, case, _packet_view())
    assert case.status == "ANALYZED"
    assert shown.ticket is not None
    assert shown.ticket.disposition == "PREVIEW"
    assert shown.ticket.queue == "READY"
    assert [item.draft_type for item in shown.drafts] == [
        "MINUTES",
        "EXPLANATION_REQUEST",
        "DECISION",
        "TICKET",
    ]
    assert {item.status for item in shown.drafts} == {"PREVIEW"}
    body = json.loads(shown.drafts[-1].content)
    assert body["legal"]["code"] is None
    assert body["facts"]["absence_days"] == "5 ngày trong 30 ngày"
    assert shown.sanction_type == "DISMISSAL"

    held = with_packet(_packet_view(sanction_type=None, risk_level="HIGH"), [])
    again = await with_preview(None, case, held)
    assert again.ticket is not None
    assert again.ticket.disposition == "HOLD"
    assert [item.draft_type for item in again.drafts] == ["MINUTES"]
    assert again.drafts[0].status == "PREVIEW"
    assert "Kết quả đánh giá" in again.drafts[0].content


@pytest.mark.asyncio
async def test_send_ticket_stores_the_legal_code(monkeypatch):
    actor = User(id=uuid4(), email="hr.preview@example.com", password_hash="x", role="HR", is_active=True)
    case = Case(
        id=uuid4(),
        case_code="C-SEND",
        created_by=actor.id,
        status="ANALYZED",
        incident_date=date(2026, 3, 1),
        employee_name="An",
        employee_code="NV-1",
        description="Nghỉ không phép",
    )
    view = _packet_view(case_status="ANALYZED").model_copy(update={"case_id": case.id})
    recommendation = Recommendation(
        id=view.recommendation_id,
        case_id=case.id,
        recommendation="Đề xuất.",
        status="DRAFT",
    )
    session = _SendSession(case, recommendation)

    async def rows(session, case_id):
        return [
            _Fact("contract_type", "xác định thời hạn"),
            _Fact("absence_days", "5 ngày trong 30 ngày"),
            _Fact("notice_form", "không báo"),
            _Fact("minutes_made", "true"),
            _Fact("explanation_requested", "true"),
        ]

    async def active(session, case_id):
        return SimpleNamespace(id=uuid4())

    async def stored(session, loaded):
        return view.model_copy(update={"case_status": loaded.status})

    legal = User(id=uuid4(), email="legal.demo@vinuni.edu.vn", password_hash="x", role="LEGAL", is_active=True)

    async def officer(session, email):
        assert email == "legal.demo@vinuni.edu.vn"
        return legal

    monkeypatch.setattr("src.features.answer.model.send.list_fact_rows", rows)
    monkeypatch.setattr("src.features.answer.model.send.active_conversation", active)
    monkeypatch.setattr("src.features.answer.model.answers.load_stored", stored)
    monkeypatch.setattr("src.features.answer.model.send.find_legal_officer", officer)
    fresh = await send_ticket(session, actor, case.id, "legal.demo@vinuni.edu.vn")
    assert session.committed == 1
    assert case.status == "PENDING_LEGAL"
    assert recommendation.status == "PENDING_REVIEW"
    assert fresh.case_status == "PENDING_LEGAL"
    drafts = [row for row in session.added if isinstance(row, CaseDraft)]
    assert [row.draft_type for row in drafts] == [
        "MINUTES",
        "EXPLANATION_REQUEST",
        "DECISION",
        "TICKET",
    ]
    body = json.loads(drafts[-1].content)
    assert body["legal"]["code"] == "legal.demo@vinuni.edu.vn"
    assert body["employee"]["code"] == "NV-1"
    notes = [row for row in session.added if isinstance(row, Message)]
    assert notes[-1].message_metadata["kind"] == "dispatch_submit"
    assert notes[-1].message_metadata["legal_code"] == "legal.demo@vinuni.edu.vn"
    runs = [row for row in session.added if isinstance(row, AgentRun)]
    assert runs[-1].status == "SUCCEEDED"
    assert runs[-1].model == "hr-help-dispatch"


def _held_send(monkeypatch, *, confirmed: bool, sanction_type: str | None = None):
    actor = User(id=uuid4(), email="hr.preview@example.com", password_hash="x", role="HR", is_active=True)
    case = Case(
        id=uuid4(),
        case_code="C-HOLD",
        created_by=actor.id,
        status="ANALYZED",
        incident_date=date(2026, 3, 1),
        employee_name="An",
        employee_code="NV-1",
        description="Nghỉ không phép",
    )
    view = _packet_view(case_status="ANALYZED", sanction_type=sanction_type, risk_level="HIGH").model_copy(
        update={"case_id": case.id}
    )
    recommendation = Recommendation(
        id=view.recommendation_id,
        case_id=case.id,
        recommendation="Đề xuất.",
        status="DRAFT",
    )
    session = _SendSession(case, recommendation)

    async def rows(session, case_id):
        return [_Fact("absence_days", "5 ngày")]

    async def active(session, case_id):
        return SimpleNamespace(id=uuid4())

    async def stored(session, loaded):
        return view.model_copy(update={"case_status": loaded.status})

    async def officer(session, email):
        return User(id=uuid4(), email=email, password_hash="x", role="LEGAL", is_active=True)

    async def is_confirmed(session, case_id):
        return confirmed

    monkeypatch.setattr("src.features.answer.model.send.list_fact_rows", rows)
    monkeypatch.setattr("src.features.answer.model.send.active_conversation", active)
    monkeypatch.setattr("src.features.answer.model.answers.load_stored", stored)
    monkeypatch.setattr("src.features.answer.model.send.find_legal_officer", officer)
    monkeypatch.setattr("src.features.answer.model.send._assessment_confirmed", is_confirmed)
    return session, actor, case, view


@pytest.mark.asyncio
async def test_confirmed_hold_sends_a_ticket_without_a_locked_sanction(monkeypatch):
    session, actor, case, view = _held_send(monkeypatch, confirmed=True)
    fresh = await send_ticket(session, actor, case.id, "legal.demo@vinuni.edu.vn")
    assert case.status == "PENDING_LEGAL"
    assert fresh.case_status == "PENDING_LEGAL"
    drafts = [row for row in session.added if isinstance(row, CaseDraft)]
    assert [row.draft_type for row in drafts] == ["MINUTES", "EXPLANATION_REQUEST", "DECISION", "TICKET"]
    body = json.loads(drafts[-1].content)
    assert body["legal"]["code"] == "legal.demo@vinuni.edu.vn"
    assert body["violation"]["sanction_type"] is None
    assert view.sanction_type is None


@pytest.mark.asyncio
async def test_unconfirmed_hold_does_not_send_a_ticket(monkeypatch):
    session, actor, case, _view = _held_send(monkeypatch, confirmed=False)
    with pytest.raises(AppError) as caught:
        await send_ticket(session, actor, case.id, "legal.demo@vinuni.edu.vn")
    assert caught.value.code == "DISPATCH_HOLD"
    assert case.status == "ANALYZED"
    assert session.committed == 0


@pytest.mark.asyncio
async def test_confirmed_termination_still_does_not_send(monkeypatch):
    session, actor, case, _view = _held_send(monkeypatch, confirmed=True, sanction_type="TERMINATION")
    with pytest.raises(AppError) as caught:
        await send_ticket(session, actor, case.id, "legal.demo@vinuni.edu.vn")
    assert caught.value.code == "DISPATCH_HOLD"
    assert case.status == "ANALYZED"


@pytest.mark.asyncio
async def test_confirmed_hold_preview_shows_the_ticket_draft(monkeypatch):
    case = Case(
        id=uuid4(),
        case_code="C-HOLD-PREVIEW",
        created_by=uuid4(),
        status="ANALYZED",
        incident_date=date(2026, 3, 1),
        employee_name="An",
        description="Nghỉ không phép",
    )

    async def rows(session, case_id):
        return [_Fact("absence_days", "5 ngày")]

    async def confirmed(session, case_id):
        return True

    monkeypatch.setattr("src.features.answer.model.send.list_fact_rows", rows)
    monkeypatch.setattr("src.features.answer.model.send._assessment_confirmed", confirmed)
    shown = await with_preview(None, case, with_packet(_packet_view(sanction_type=None, risk_level="HIGH"), []))
    assert shown.ticket is not None
    assert shown.ticket.disposition == "HOLD"
    assert shown.ticket.hold_code == "OPEN_SANCTION"
    assert [item.draft_type for item in shown.drafts] == [
        "MINUTES",
        "EXPLANATION_REQUEST",
        "DECISION",
        "TICKET",
    ]


@pytest.mark.asyncio
async def test_chat_submit_asks_before_writing_the_ticket(monkeypatch):
    from src.features.clarify.model import turns

    case = Case(
        id=uuid4(),
        case_code="C-ASK",
        created_by=uuid4(),
        status="ANALYZED",
        incident_date=date(2026, 3, 1),
        employee_code="NV-1",
    )
    view = _packet_view(case_status="ANALYZED").model_copy(update={"case_id": case.id})
    recommendation = Recommendation(
        id=view.recommendation_id,
        case_id=case.id,
        recommendation="Đề xuất.",
        status="DRAFT",
    )
    notes = []

    class _ChatSession:
        async def get(self, model, key):
            assert model is Recommendation
            assert key == recommendation.id
            return recommendation

        def add(self, row) -> None:
            return None

        async def flush(self) -> None:
            return None

    async def add_message(session, draft):
        notes.append(draft)
        return Message(
            id=uuid4(),
            conversation_id=draft.conversation_id,
            role=draft.role,
            content=draft.content,
            message_metadata=draft.metadata,
        )

    async def start_run(session, conversation_id, message_id, model):
        return AgentRun(
            id=uuid4(),
            conversation_id=conversation_id,
            message_id=message_id,
            status="RUNNING",
            model=model,
            started_at=utc_now(),
        )

    async def attach_packet(session, answer):
        return with_packet(answer, [])

    async def preview(session, loaded, packed):
        assert loaded.status == "ANALYZED"
        ticket = DraftView(
            draft_id=uuid4(),
            draft_type="TICKET",
            title="Phiếu chuyển pháp chế",
            content='{"legal": {"code": null}}',
            status="PREVIEW",
        )
        return with_packet(packed, [ticket])

    async def explode(*args, **kwargs):
        raise AssertionError("Lượt chat không được ghi phiếu.")

    monkeypatch.setattr(turns, "add_message", add_message)
    monkeypatch.setattr(turns, "start_run", start_run)
    monkeypatch.setattr(turns, "attach_packet", attach_packet)
    monkeypatch.setattr(turns, "with_preview", preview)
    monkeypatch.setattr("src.features.answer.model.release.save_submission", explode)
    monkeypatch.setattr(turns, "save_submission", explode, raising=False)
    answer, run_id, text = await turns._dispatch(
        _ChatSession(),
        case,
        SimpleNamespace(id=uuid4()),
        _handoff([]),
        view,
        uuid4(),
    )
    assert text == ask_to_send()
    assert "email pháp chế" in text
    assert case.status == "ANALYZED"
    assert recommendation.status == "DRAFT"
    assert notes[-1].metadata["kind"] == "dispatch_preview"
    assert answer.ticket is not None
    assert answer.ticket.disposition == "PREVIEW"
    assert run_id is not None
