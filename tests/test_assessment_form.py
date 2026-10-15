"""The assessment form is assembled from stored facts. It does not send a ticket."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
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
from src.models.cases import Case


@pytest.mark.asyncio
async def test_assessment_preview_date_comes_from_case_creation(monkeypatch):
    from src.features.assessment import service

    sections, _sources = compose(_source(confirmed=True, sanction="REPRIMAND"))
    case = Case(id=uuid4(), case_code="case-099", status="ANALYZED", created_at=datetime(2026, 10, 15, 18, 30))
    report = SimpleNamespace(id=uuid4(), recommendation_id=None)
    version = SimpleNamespace(
        version=1, status="DRAFT", source="AI", created_at=datetime(2026, 10, 20),
        payload={"sections": sections.model_dump(mode="json")},
    )
    monkeypatch.setattr(service, "load", AsyncMock(return_value=None))
    view = await service._present(AsyncMock(), SimpleNamespace(role="HR"), case, report, version)
    assert view.metadata.case_created_date == date(2026, 10, 16)
    assert view.metadata.generated_at == datetime(2026, 10, 20)
    assert view.metadata.minutes_profile.document_number == "CASE-099/2026/BB-XLKL"
    assert view.metadata.minutes_profile.company_name == "TẬP ĐOÀN VINGROUP – CÔNG TY CP"


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


def test_incident_narrative_is_minutes_bullets_not_the_raw_ai_report():
    sections, _sources = compose(_source(confirmed=True, sanction="REPRIMAND"))

    narrative = sections.incident_summary.narrative
    assert narrative.startswith("- Đi muộn nhiều lần.")
    assert "- Số lần đi muộn: 5." in narrative
    assert "BIÊN BẢN ĐÁNH GIÁ" not in narrative
    assert "Chunk_id" not in narrative
    assert "I. " not in narrative


def test_employee_department_and_position_are_read_from_case_description():
    sections, _sources = compose(_source(confirmed=True, sanction="REPRIMAND", description="Phòng ban: SOFTWARE\nChức danh: DEVELOPER\nVi phạm: Đi muộn 10 ngày.\nNhân viên đi muộn liên tục."))

    assert sections.employee_information.department == "SOFTWARE"
    assert sections.employee_information.position == "DEVELOPER"
    assert "Phòng ban" not in sections.incident_summary.narrative
    assert "Chức danh" not in sections.incident_summary.narrative
    assert "- Đi muộn 10 ngày." in sections.incident_summary.narrative


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


def test_deepseek_chat_kwargs_use_the_deepseek_key(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "deepseek-test")
    monkeypatch.setattr(settings, "DEEPSEEK_BASE_URL", "")
    monkeypatch.setattr(settings, "MODEL_NAME", "deepseek-flash")
    monkeypatch.setattr(settings, "FALLBACK_MODEL_NAME", "deepseek-chat")
    kwargs = settings.chat_kwargs("deepseek-chat")
    assert kwargs["base_url"] == "https://api.deepseek.com"
    assert kwargs["model"] == "deepseek-chat"
    assert kwargs["api_key"] == "deepseek-test"
    assert settings.chat_models() == ("deepseek-flash", "deepseek-chat")


def test_hr_cannot_send_a_citation_or_a_sanction_code():
    with pytest.raises(ValidationError):
        AssessmentPatch.model_validate({"citations": []})
    with pytest.raises(ValidationError):
        AssessmentPatch.model_validate(
            {"handling_proposal": {"proposed_actions": [{"code": "DISMISSAL", "label": "Sa thải"}]}}
        )


def _source(*, confirmed: bool, sanction: str, description: str = "Đi muộn nhiều lần.") -> ComposeInput:
    return ComposeInput(
        case_code="C-1",
        case_status="ANALYZED",
        family="LATE",
        incident_date=date(2026, 3, 1),
        description=description,
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
        message=(
            "BIÊN BẢN ĐÁNH GIÁ VỤ VIỆC I. THÔNG TIN VỤ VIỆC - Nhân viên: Nguyễn Văn A. "
            "II. CĂN CỨ ĐÁNH GIÁ - Chunk_id: 5d8458e0-04af-44fa-970c-157922461604."
        ),
        legal_basis=[],
        internal_rule=[],
        precedent=[],
        inspection_risk=[],
        standard=applied_standard(sanction if sanction != "TERMINATION" else None, "LOW", []),
    )
