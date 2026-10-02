"""The assessment form is assembled from stored facts. It does not send a ticket."""

from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.core.config import settings
from src.features.answer.model.standard import applied_standard
from src.features.answer.schema import AnswerView
from src.features.assessment.agent import ComposeInput, FactInput, compose
from src.features.assessment.schemas import AssessmentPatch, EvidenceCard
from src.features.assessment.service import ticket_allowed
from src.features.assessment.validator import validate_sections
from src.features.clarify.model.catalog import required_specs, resolved_family


def test_a_confirmed_hold_can_open_the_legal_ticket():
    assert ticket_allowed(True, "ANALYZED", "HOLD", None) is True
    assert ticket_allowed(True, "ANALYZED", "PREVIEW", "REPRIMAND") is True
    assert ticket_allowed(False, "ANALYZED", "HOLD", None) is False
    assert ticket_allowed(True, "ANALYZED", "HOLD", "TERMINATION") is False
    assert ticket_allowed(True, "PENDING_LEGAL", "SUBMIT", "REPRIMAND") is False


def test_a_missing_required_fact_blocks_confirm():
    sections, _sources = compose(_source(confirmed=False, sanction="WARNING"))
    result = validate_sections(sections)
    assert result.is_valid is False
    assert result.blocking_errors
    assert sections.handling_proposal.proposed_actions == []


def test_a_supported_level_stays_a_proposal():
    sections, _sources = compose(_source(confirmed=True, sanction="REPRIMAND"))
    result = validate_sections(sections)
    assert result.is_valid is True
    assert sections.assessment_result.status == "SUPPORTED"
    assert sections.handling_proposal.proposed_actions[0].code == "REPRIMAND"
    assert sections.handling_proposal.proposed_actions[0].label == "Cảnh cáo"


def test_termination_is_not_offered_as_a_company_level():
    sections, _sources = compose(_source(confirmed=True, sanction="TERMINATION"))
    assert sections.handling_proposal.proposed_actions == []
    assert sections.assessment_result.status == "INSUFFICIENT_EVIDENCE"


def test_a_citation_outside_the_stored_evidence_blocks_confirm():
    sections, _sources = compose(_source(confirmed=True, sanction="WARNING"))
    forged = EvidenceCard(
        evidence_id="EV-999",
        chunk_id=uuid4(),
        title="Văn bản không có trong hồ sơ",
        citation_label="Điều bịa",
        quote="không có trong retrieval",
        layer="legal_basis",
    )
    dirty = sections.model_copy(update={"citations": [*sections.citations, forged]})
    result = validate_sections(dirty)
    assert result.is_valid is False
    assert any("không nằm trong văn bản" in item for item in result.blocking_errors)


def test_an_absence_narrative_does_not_ask_for_late_days():
    family = resolved_family("Vi phạm: nghỉ không phép 5 ngày liên tục", "LATE")
    keys = [spec.key for spec in required_specs(family)]
    assert family == "UNAUTHORIZED_ABSENCE"
    assert "absence_days" in keys
    assert "notice_form" in keys
    assert "late_days" not in keys


def test_a_generic_narrative_keeps_the_stored_family():
    assert resolved_family("Vi phạm nội quy", "LATE") == "LATE"
    assert resolved_family("", None) == "GENERAL"


def test_an_openrouter_key_is_not_sent_to_openai(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-or-test")
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", "")
    monkeypatch.setattr(settings, "MODEL_NAME", "gpt-4o-mini")
    kwargs = settings.openai_chat_kwargs()
    assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert kwargs["model"] == "openai/gpt-4o-mini"
    assert kwargs["api_key"] == "sk-or-test"


def test_hr_cannot_send_a_citation_or_a_sanction_code():
    with pytest.raises(ValidationError):
        AssessmentPatch.model_validate({"citations": []})
    with pytest.raises(ValidationError):
        AssessmentPatch.model_validate(
            {"handling_proposal": {"proposed_actions": [{"code": "DISMISSAL", "label": "Sa thải"}]}}
        )


def _source(*, confirmed: bool, sanction: str) -> ComposeInput:
    return ComposeInput(
        case_code="C-1",
        case_status="ANALYZED",
        family="LATE",
        incident_date=date(2026, 3, 1),
        description="Đi muộn nhiều lần.",
        employee_code="E-1",
        employee_name="Nguyễn Văn A",
        facts=(FactInput("late_days", "Số lần đi muộn", "5" if confirmed else None, confirmed, True),),
        answer=_answer(sanction),
    )


def _answer(sanction: str) -> AnswerView:
    return AnswerView(
        recommendation_id=uuid4(),
        case_id=uuid4(),
        case_status="ANALYZED",
        agent_run_id=uuid4(),
        rationale="Mức lấy từ nội quy và luật đã truy xuất.",
        sanction_type=sanction,
        process_steps=[],
        risk_level="LOW",
        missing_internal_rule=False,
        message="BIÊN BẢN ĐÁNH GIÁ VỤ VIỆC",
        legal_basis=[],
        internal_rule=[],
        precedent=[],
        inspection_risk=[],
        standard=applied_standard(sanction if sanction != "TERMINATION" else None, "LOW", []),
    )
