"""Returned minutes preserve reviewer feedback and open as editable HR drafts."""

import os
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.common.deps import get_session
from src.core.config import settings
from src.core.security.auth_handler import AuthHandler
from src.core.security.tokens import claims_for_role
from src.features.assessment import service
from src.features.assessment.schemas import EvidenceCard, Sections
from src.features.assessment.validator import validate_sections
from src.features.legal_review.model import service as review_service
from src.main import app
from src.models.assessment_reports import AssessmentReport, AssessmentVersion
from src.models.case_drafts import CaseDraft
from src.models.cases import Case
from src.models.conversations import Conversation
from src.models.recommendation_citations import RecommendationCitation
from src.models.recommendations import Recommendation
from src.models.users import User


def _sections(code="TEST-RETURN", status="REJECTED"):
    card = EvidenceCard(
        evidence_id="EV-001",
        chunk_id=uuid4(),
        title="Nguồn đã lưu",
        citation_label="Điều 1",
        quote="Trích dẫn đã lưu.",
        article="1",
        layer="internal_rule",
    )
    return Sections.model_validate(
        {
            "case_information": {"case_code": code, "case_status": status, "incident_date": "2026-10-01"},
            "employee_information": {"employee_name": "Nhân viên thử", "employee_code": "TEST-EMP"},
            "incident_summary": {"narrative": "Nội dung HR đã sửa trước khi gửi."},
            "confirmed_facts": [
                {
                    "fact_key": "late_days",
                    "label": "Số lần đi muộn",
                    "value": "5",
                    "status": "CONFIRMED",
                    "blocking": False,
                }
            ],
            "evidence_reviewed": [card.model_dump(mode="json")],
            "assessment": {},
            "assessment_result": {"status": "INSUFFICIENT_EVIDENCE", "summary": "Cần rà soát."},
            "handling_proposal": {"rationale": "Ý kiến HR đã lưu."},
            "risk_and_gaps": {},
            "next_steps": [],
            "citations": [card.model_dump(mode="json")],
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("newest", ["MANAGER", "LEGAL"])
async def test_latest_return_reason_chooses_most_recent_reviewer(monkeypatch, newest):
    now = datetime(2026, 10, 16, 7)
    audit = SimpleNamespace(
        action="MANAGER_REJECTED", actor_id=uuid4(), created_at=now, audit_metadata={"comment": "Bổ sung mức xử lý"}
    )
    review = SimpleNamespace(
        reviewer_id=uuid4(),
        decided_at=now + timedelta(minutes=1 if newest == "LEGAL" else -1),
        comment="Bổ sung giải trình",
    )
    case = SimpleNamespace(id=uuid4())
    session = SimpleNamespace(
        get=AsyncMock(side_effect=[case, SimpleNamespace(full_name="Người duyệt")]),
        scalar=AsyncMock(side_effect=[audit, review]),
    )
    monkeypatch.setattr(review_service, "require_case_access", AsyncMock())
    result = await review_service.latest_return_reason(session, SimpleNamespace(), case.id)
    assert result.reviewer_role == newest
    assert result.comment == (review.comment if newest == "LEGAL" else audit.audit_metadata["comment"])
    assert result.reviewer_name == "Người duyệt"


def test_archived_citation_quote_is_preserved_but_missing_source_is_not_invented():
    sections = _sections()
    original = sections.citations[0]
    archived = SimpleNamespace(chunk_id=None, quote=original.quote, article=original.article, clause=None, point=None)
    answer = SimpleNamespace(legal_basis=[], internal_rule=[archived], precedent=[], inspection_risk=[])
    revised = service._align_saved_citations(sections, answer)
    assert revised.citations[0].chunk_id is None
    assert revised.citations[0].quote == original.quote
    assert sections.citations[0].chunk_id == original.chunk_id
    assert validate_sections(revised, set()).is_valid
    forged = sections.model_copy(
        update={"citations": [original.model_copy(update={"quote": "Trích dẫn không có trong hồ sơ"})]}
    )
    assert not validate_sections(service._align_saved_citations(forged, answer), set()).is_valid


def test_get_does_not_replace_manual_hr_draft_with_ai_composition():
    assert (
        service._can_refresh(
            SimpleNamespace(role="HR"), SimpleNamespace(status="ANALYZED"), SimpleNamespace(status="DRAFT", source="HR")
        )
        is False
    )


@pytest.mark.skipif(os.getenv("P029_RUN_DB_TESTS") != "1", reason="Requires migrated local PostgreSQL")
@pytest.mark.asyncio
@pytest.mark.parametrize("reviewer_role", ["MANAGER", "LEGAL"])
async def test_return_edit_confirm_and_resend_preserves_old_minutes(reviewer_role, monkeypatch):
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI)
    suffix = uuid4().hex
    ids = {key: uuid4() for key in ("hr", "manager", "legal", "case", "rec", "report", "version")}
    old_status = "APPROVED" if reviewer_role == "MANAGER" else "PENDING_LEGAL"
    code = f"TEST-RETURN-{suffix}"
    sections = _sections(code, old_status)
    previous_overrides = app.dependency_overrides.copy()
    monkeypatch.setattr(
        service,
        "_compose_case",
        AsyncMock(side_effect=AssertionError("Manual revision must not compose another report")),
    )
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False, autoflush=False
                ) as session:
                    for role in ("HR", "MANAGER", "LEGAL"):
                        session.add(
                            User(
                                id=ids[role.lower()],
                                email=f"{role.lower()}-{suffix}@example.invalid",
                                full_name=role,
                                password_hash="test-only",
                                role=role,
                            )
                        )
                    await session.flush()
                    session.add(
                        Case(
                            id=ids["case"],
                            case_code=code,
                            created_by=ids["hr"],
                            status=old_status,
                            incident_date=date(2026, 10, 1),
                            family="LATE",
                        )
                    )
                    await session.flush()
                    session.add(Conversation(user_id=ids["hr"], case_id=ids["case"], status="ACTIVE"))
                    session.add(
                        Recommendation(
                            id=ids["rec"],
                            case_id=ids["case"],
                            recommendation="Saved recommendation",
                            status="APPROVED" if reviewer_role == "MANAGER" else "PENDING_REVIEW",
                        )
                    )
                    await session.flush()
                    session.add(
                        RecommendationCitation(
                            recommendation_id=ids["rec"], quote=sections.citations[0].quote, article="1", chunk_id=None
                        )
                    )
                    session.add(
                        AssessmentReport(
                            id=ids["report"],
                            case_id=ids["case"],
                            recommendation_id=ids["rec"],
                            status="CONFIRMED",
                            current_version=1,
                        )
                    )
                    for kind in ("MINUTES", "EXPLANATION_REQUEST", "DECISION", "TICKET"):
                        session.add(
                            CaseDraft(
                                case_id=ids["case"],
                                recommendation_id=ids["rec"],
                                created_by=ids["hr"],
                                draft_type=kind,
                                title=kind,
                                content="Old packet",
                                status="APPROVED" if reviewer_role == "MANAGER" else "PENDING_REVIEW",
                            )
                        )
                    await session.flush()
                    session.add(
                        AssessmentVersion(
                            id=ids["version"],
                            report_id=ids["report"],
                            version=1,
                            status="CONFIRMED",
                            source="HR",
                            edited_by=ids["hr"],
                            payload={"sections": sections.model_dump(mode="json"), "sources": {}},
                        )
                    )
                    await session.commit()

                    async def test_session():
                        yield session

                    app.dependency_overrides[get_session] = test_session

                    def auth(role):
                        token = AuthHandler.create_access_token(
                            {"user_id": str(ids[role.lower()]), "is_active": True}, **claims_for_role(role)
                        )
                        return {"Authorization": f"Bearer {token}"}

                    root = f"/api/v1/cases/{ids['case']}"
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        target = (
                            f"/api/v1/manager/cases/{ids['case']}/reject"
                            if reviewer_role == "MANAGER"
                            else f"{root}/reviews"
                        )
                        response = await client.post(
                            target,
                            headers=auth(reviewer_role),
                            json={
                                "comment": "Sửa diễn biến theo giải trình mới",
                                **({"decision": "REJECT"} if reviewer_role == "LEGAL" else {}),
                            },
                        )
                        assert response.status_code == 200, response.text
                        reason = await client.get(f"{root}/returns/latest", headers=auth("HR"))
                        assert reason.json()["reviewer_role"] == reviewer_role
                        assert reason.json()["comment"] == "Sửa diễn biến theo giải trình mới"
                        revision = await client.post(f"{root}/assessment/reanalyze", headers=auth("HR"))
                        assert revision.status_code == 200, revision.text
                        doc = revision.json()
                        assert doc["status"] == "DRAFT" and doc["permissions"]["can_edit"]
                        assert doc["metadata"]["source"] == "HR"
                        assert doc["sections"]["incident_summary"]["narrative"] == sections.incident_summary.narrative
                        assert doc["sections"]["citations"][0]["chunk_id"] is None
                        edited = await client.post(
                            f"{root}/assessment/save",
                            headers=auth("HR"),
                            json={
                                "incident_summary": {"narrative": "Diễn biến HR đã sửa theo yêu cầu trả lại."},
                                "handling_rationale": "Đề xuất HR đã sửa.",
                            },
                        )
                        assert edited.status_code == 200, edited.text
                        read = await client.get(f"{root}/assessment", headers=auth("HR"))
                        assert (
                            read.json()["sections"]["incident_summary"]["narrative"]
                            == "Diễn biến HR đã sửa theo yêu cầu trả lại."
                        )
                        confirmed = await client.post(f"{root}/assessment/confirm", headers=auth("HR"))
                        assert confirmed.status_code == 200, confirmed.text
                        assert confirmed.json()["permissions"]["can_create_ticket"]
                        sent = await client.post(
                            f"{root}/ticket", headers=auth("HR"), json={"legal_code": f"legal-{suffix}@example.invalid"}
                        )
                        assert sent.status_code == 200, sent.text
                        assert sent.json()["case_status"] == "PENDING_LEGAL"
                        packet = await client.get(f"{root}/review-pack", headers=auth("LEGAL"))
                        assert packet.status_code == 200, packet.text
                        assert (
                            packet.json()["assessment"]["sections"]["incident_summary"]["narrative"]
                            == "Diễn biến HR đã sửa theo yêu cầu trả lại."
                        )
                    original = await session.get(AssessmentVersion, ids["version"])
                    assert original.status == "CONFIRMED"
                    assert (
                        original.payload["sections"]["incident_summary"]["narrative"]
                        == sections.incident_summary.narrative
                    )
                    assert (await session.get(Recommendation, ids["rec"])).status == "SUPERSEDED"
                    service._compose_case.assert_not_awaited()
            finally:
                await transaction.rollback()
        async with AsyncSession(engine) as verify:
            assert await verify.get(Case, ids["case"]) is None
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        await engine.dispose()


def test_manual_handling_text_survives_the_minutes_document():
    from src.features.answer.model.case_tools import disciplinary_minutes_document
    from src.features.assessment.schemas import AssessmentPatch

    sections, _ = service._merge(_sections(), {}, AssessmentPatch(handling_rationale="HR đề nghị xác minh thêm."))
    assert sections.handling_proposal.manual_text == "HR đề nghị xác minh thêm."
    case = Case(id=uuid4(), case_code="TEST-RETURN", created_at=datetime(2026, 10, 16))
    document = disciplinary_minutes_document(case, None, sections)
    assert "HR đề nghị xác minh thêm." in document.content
