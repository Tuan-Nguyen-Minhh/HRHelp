"""Workflow rules that do not need a database: transitions, contracts, and routes."""

import pytest
from pydantic import ValidationError

from src.common.errors import AppError, error_body
from src.common.idempotency import request_hash
from src.common.redact import redact
from src.common.workflow import TRANSITIONS, assert_transition
from src.features.accounts.schema import StaffCreate, StaffUpdate
from src.features.decision.schema import IssueDecisionRequest, PrecedentRequest
from src.features.knowledge.model import split_chunks
from src.features.legal_review.schema import ReviewRequest
from src.main import app
from src.models.audit_logs import AUDIT_ACTIONS


def test_state_machine_allows_the_human_loop():
    assert_transition("OPEN", "NEED_INFO")
    assert_transition("OPEN", "ANALYZED")
    assert_transition("NEED_INFO", "ANALYZED")
    assert_transition("ANALYZED", "PENDING_LEGAL")
    assert_transition("ANALYZED", "APPROVED")
    assert_transition("PENDING_LEGAL", "APPROVED")
    assert_transition("PENDING_LEGAL", "REJECTED")
    assert_transition("REJECTED", "NEED_INFO")
    assert_transition("REJECTED", "ANALYZED")
    assert_transition("APPROVED", "DECIDED")
    assert_transition("APPROVED", "REJECTED")
    assert_transition("DECIDED", "CLOSED")
    assert TRANSITIONS["CLOSED"] == frozenset()


def test_illegal_transition_is_a_conflict():
    with pytest.raises(AppError) as raised:
        assert_transition("OPEN", "DECIDED")
    assert raised.value.status_code == 409
    assert raised.value.code == "INVALID_CASE_TRANSITION"
    assert raised.value.details == {"from": "OPEN", "to": "DECIDED"}


def test_error_envelope_keeps_the_legacy_detail():
    body = error_body("CASE_NOT_FOUND", "Không tìm thấy hồ sơ.", {"case_id": "x"}, "req-1")
    assert body["detail"] == "Không tìm thấy hồ sơ."
    assert body["error"]["code"] == "CASE_NOT_FOUND"
    assert body["error"]["request_id"] == "req-1"
    assert body["error"]["details"] == {"case_id": "x"}


def test_redact_strips_secrets_and_bearer_tokens():
    cleaned = redact(
        {
            "password": "secret-value",
            "headers": {"Authorization": "Bearer abc.def"},
            "note": "Bearer should-hide",
            "nested": [{"api_key": "sk-test"}],
        }
    )
    assert cleaned["password"] == "[REDACTED]"
    assert cleaned["headers"]["Authorization"] == "[REDACTED]"
    assert cleaned["note"] == "[REDACTED]"
    assert cleaned["nested"][0]["api_key"] == "[REDACTED]"


def test_request_hash_ignores_key_order():
    assert request_hash({"b": 1, "a": 2}) == request_hash({"a": 2, "b": 1})


def test_review_body_cannot_carry_a_sanction():
    body = ReviewRequest(decision="APPROVE", comment="đồng ý")
    assert body.decision == "APPROVE"
    with pytest.raises(ValidationError):
        ReviewRequest(decision="APPROVE", sanction_type="DISMISSAL")
    with pytest.raises(ValidationError):
        ReviewRequest(decision="MAYBE")
    with pytest.raises(ValidationError):
        ReviewRequest(decision="REJECT")


def test_decision_body_has_no_sanction_field():
    body = IssueDecisionRequest(decision_code="QD-01", summary="Kỷ luật theo đề xuất đã duyệt")
    assert "sanction_type" not in body.model_dump()
    with pytest.raises(ValidationError):
        IssueDecisionRequest(decision_code="QD-01", summary="x", sanction_type="DISMISSAL")


def test_staff_account_role_stays_hr_or_legal():
    created = StaffCreate(email="HR.New@vinuni.edu.vn", password="Demo-hr-2026", role="LEGAL")
    assert created.email == "hr.new@vinuni.edu.vn"
    with pytest.raises(ValidationError):
        StaffCreate(email="a@vinuni.edu.vn", password="short", role="HR")
    with pytest.raises(ValidationError):
        StaffCreate(email="a@vinuni.edu.vn", password="Demo-hr-2026", role="MANAGER")
    with pytest.raises(ValidationError):
        StaffUpdate()
    changed = StaffUpdate(role="HR", is_active=False)
    assert changed.role == "HR"
    assert changed.is_active is False


def test_empty_precedent_summary_is_rejected():
    with pytest.raises(ValidationError):
        PrecedentRequest(precedent_summary="   ")


def test_chunks_follow_blank_lines_then_the_size_limit():
    pieces = split_chunks("đoạn một\n\n" + ("a" * 20), limit=10)
    assert pieces[0] == "đoạn một"
    assert "".join(pieces[1:]) == "a" * 20
    assert all(len(part) <= 10 for part in pieces[1:])


def test_audit_catalog_covers_the_human_decisions():
    for action in (
        "LEGAL_TICKET_SUBMITTED",
        "HR_ESCALATED",
        "LEGAL_APPROVED",
        "LEGAL_REJECTED",
        "MANAGER_REJECTED",
        "CASE_REOPENED",
        "DECISION_ISSUED",
        "PRECEDENT_CREATED",
        "CASE_CLOSED",
    ):
        assert action in AUDIT_ACTIONS


def test_enterprise_routes_are_mounted():
    paths = set(app.openapi()["paths"])
    expected = {
        "/health",
        "/ready",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/cases",
        "/api/v1/cases/{case_id}/messages",
        "/api/v1/cases/{case_id}/facts/confirm",
        "/api/v1/cases/{case_id}/ticket",
        "/api/v1/legal-officers",
        "/api/v1/cases/{case_id}/escalate",
        "/api/v1/cases/{case_id}/assessment",
        "/api/v1/cases/{case_id}/assessment/generate",
        "/api/v1/cases/{case_id}/assessment/save",
        "/api/v1/cases/{case_id}/assessment/confirm",
        "/api/v1/cases/{case_id}/assessment/reanalyze",
        "/api/v1/legal/reviews/queue",
        "/api/v1/cases/{case_id}/review-pack",
        "/api/v1/cases/{case_id}/reviews",
        "/api/v1/cases/{case_id}/reviews/latest",
        "/api/v1/manager/queue",
        "/api/v1/manager/cases/{case_id}/review-pack",
        "/api/v1/manager/cases/{case_id}/reject",
        "/api/v1/manager/users",
        "/api/v1/manager/users/{user_id}",
        "/api/v1/cases/{case_id}/reopen",
        "/api/v1/cases/{case_id}/decision-preview",
        "/api/v1/cases/{case_id}/decisions",
        "/api/v1/cases/{case_id}/decisions/precedent",
        "/api/v1/cases/{case_id}/close",
        "/api/v1/cases/{case_id}/timeline",
        "/api/v1/cases/{case_id}/recidivism",
        "/api/v1/cases/{case_id}/export/assessment",
        "/api/v1/cases/{case_id}/export/ticket",
        "/api/v1/cases/{case_id}/export/decision",
        "/api/v1/policies/{policy_id}/versions",
        "/api/v1/documents/{document_id}/retry",
        "/api/v1/notifications",
        "/api/v1/notifications/{notification_id}/read",
        "/api/v1/dashboard/summary",
        "/api/v1/dashboard/cases",
        "/api/v1/dashboard/processing-time",
        "/api/v1/dashboard/sanctions",
    }
    missing = expected - paths
    assert not missing


@pytest.mark.asyncio
async def test_health_and_me_error_shape(client):
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.headers.get("X-Request-ID")

    me = await client.get("/api/v1/auth/me", headers={"X-Request-ID": "req-me"})
    assert me.status_code == 401
    body = me.json()
    assert body["detail"]
    assert body["error"]["code"] == "AUTH_REQUIRED"
    assert body["error"]["request_id"] == "req-me"

    ready = await client.get("/ready")
    assert ready.status_code in {200, 503}
    checks = ready.json()["checks"]
    assert set(checks) == {"database", "pgvector", "llm_configured", "embedding_configured", "rerank_configured"}
    assert all(isinstance(value, bool) for value in checks.values())
