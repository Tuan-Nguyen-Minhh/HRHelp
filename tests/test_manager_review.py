"""Manager final review reads the saved packet and returns rejected cases to HR."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.common.errors import AppError
from src.common.idempotency import Replay
from src.features.decision.model import service
from src.features.decision.schema import IssueDecisionRequest, RejectDecisionRequest
from src.models.case_drafts import CaseDraft
from src.models.cases import Case
from src.models.disciplinary_decisions import DisciplinaryDecision
from src.models.recommendations import Recommendation


@pytest.fixture
def review(monkeypatch):
    case = Case(id=uuid4(), created_by=uuid4(), case_code="CASE-009", status="APPROVED")
    actor = SimpleNamespace(id=uuid4(), role="MANAGER")
    recommendation = Recommendation(id=uuid4(), case_id=case.id, status="APPROVED", sanction_type="WARNING")
    drafts = [
        CaseDraft(id=uuid4(), recommendation_id=recommendation.id, draft_type=kind, status="APPROVED")
        for kind in ("MINUTES", "EXPLANATION_REQUEST", "DECISION", "TICKET")
    ]
    session = SimpleNamespace(
        get=AsyncMock(return_value=case),
        scalar=AsyncMock(side_effect=[None, recommendation]),
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: drafts)),
        commit=AsyncMock(),
        flush=AsyncMock(),
        add=Mock(),
    )
    for name in ("claim", "complete", "write_audit", "notify", "lock_case"):
        monkeypatch.setattr(service, name, AsyncMock(return_value=case if name == "lock_case" else None))
    return SimpleNamespace(case=case, actor=actor, recommendation=recommendation, drafts=drafts, session=session)


@pytest.mark.parametrize("comment", ["", "   ", "\n\t"])
def test_rejection_requires_a_nonempty_reason(comment):
    with pytest.raises(ValidationError):
        RejectDecisionRequest(comment=comment)


def test_rejection_cannot_change_the_sanction():
    with pytest.raises(ValidationError):
        RejectDecisionRequest(comment="Bổ sung biên bản", sanction_type="DISMISSAL")


@pytest.mark.asyncio
async def test_reject_updates_whole_packet_and_notifies_hr_even_without_a_sanction(review):
    review.recommendation.sanction_type = None
    response = await service.reject_decision(
        review.session, review.actor, review.case.id, RejectDecisionRequest(comment="  Bổ sung căn cứ  "), "reject-1"
    )
    assert response.status == review.case.status == review.recommendation.status == "REJECTED"
    assert all(draft.status == "REJECTED" for draft in review.drafts)
    audit = service.write_audit.await_args.kwargs
    assert audit["action"] == "MANAGER_REJECTED"
    assert audit["metadata"] == {"comment": "Bổ sung căn cứ"}
    notification = service.notify.await_args.kwargs
    assert notification["user_id"] == review.case.created_by
    assert "Bổ sung căn cứ" in notification["body"]
    review.session.commit.assert_awaited_once()
    # Legal review records are neither inserted nor overwritten.
    review.session.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["HR", "LEGAL", "SIGNER", "ADMIN"])
async def test_other_roles_cannot_reject_manager_review(review, role):
    review.actor.role = role
    with pytest.raises(AppError) as raised:
        await service.reject_decision(
            review.session, review.actor, review.case.id, RejectDecisionRequest(comment="x"), None
        )
    assert raised.value.status_code == 403
    service.lock_case.assert_not_awaited()
    review.session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["PENDING_LEGAL", "REJECTED", "DECIDED", "CLOSED"])
async def test_stale_rejection_does_not_change_an_already_processed_case(review, status):
    review.case.status = status
    with pytest.raises(AppError) as raised:
        await service.reject_decision(
            review.session, review.actor, review.case.id, RejectDecisionRequest(comment="x"), None
        )
    assert raised.value.status_code == 409
    assert review.case.status == status
    assert review.recommendation.status == "APPROVED"
    service.notify.assert_not_awaited()
    review.session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reject_replays_without_second_notification(review):
    service.claim.return_value = Replay(200, {"case_id": str(review.case.id), "status": "REJECTED"})
    response = await service.reject_decision(
        review.session, review.actor, review.case.id, RejectDecisionRequest(comment="x"), "replay"
    )
    assert response.status == "REJECTED"
    service.lock_case.assert_not_awaited()
    service.notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_reject_cannot_override_an_issued_decision(review):
    review.session.scalar.side_effect = [uuid4()]
    with pytest.raises(AppError) as raised:
        await service.reject_decision(
            review.session, review.actor, review.case.id, RejectDecisionRequest(comment="x"), None
        )
    assert raised.value.code == "DECISION_ALREADY_EXISTS"
    assert review.case.status == "APPROVED"
    review.session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_manager_reads_saved_packet_without_needing_a_legal_role(review, monkeypatch):
    packet = object()
    builder = AsyncMock(return_value=packet)
    monkeypatch.setattr(service, "stored_review_pack", builder)
    assert await service.manager_review_pack(review.session, review.actor, review.case.id) is packet
    builder.assert_awaited_once_with(review.session, review.case.id)


@pytest.mark.asyncio
async def test_legal_cannot_use_manager_packet(review, monkeypatch):
    review.actor.role = "LEGAL"
    builder = AsyncMock()
    monkeypatch.setattr(service, "stored_review_pack", builder)
    with pytest.raises(AppError) as raised:
        await service.manager_review_pack(review.session, review.actor, review.case.id)
    assert raised.value.status_code == 403
    builder.assert_not_awaited()


@pytest.mark.asyncio
async def test_final_approval_preserves_stored_level_and_records_decision(review, monkeypatch):
    draft = review.drafts[2]
    bundle = AsyncMock(return_value=(review.case, review.recommendation, draft))
    monkeypatch.setattr(service, "_approved_bundle", bundle)
    review.session.scalar.side_effect = [None]

    def add_decision(row):
        assert isinstance(row, DisciplinaryDecision)
        row.id = uuid4()

    review.session.add.side_effect = add_decision
    payload = IssueDecisionRequest(decision_code="QD-009", summary="Theo biên bản HR đã xác nhận")
    result = await service.issue_decision(review.session, review.actor, review.case.id, payload, "approve-1")
    assert result.sanction_type == "WARNING"
    assert result.case_status == review.case.status == "DECIDED"
    assert draft.status == "ISSUED"
    assert result.issued_by == review.actor.id
    assert isinstance(result.issued_at, datetime)
    assert service.write_audit.await_args.kwargs["action"] == "DECISION_ISSUED"
    review.session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_level_is_an_explicit_preview_error(review):
    review.recommendation.sanction_type = None
    review.session.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: review.recommendation))
    with pytest.raises(AppError) as raised:
        await service.decision_preview(review.session, review.actor, review.case.id)
    assert raised.value.status_code == 409
    assert "chưa xác định mức kỷ luật" in raised.value.detail
