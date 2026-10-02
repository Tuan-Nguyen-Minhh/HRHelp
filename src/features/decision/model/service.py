"""Issue a decision from the approved recommendation. The client cannot pick another level."""

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.access import require_case_access
from src.common.audit import write_audit
from src.common.clock import utc_now
from src.common.errors import AppError
from src.common.idempotency import claim, complete, request_hash
from src.common.notify import notify
from src.common.workflow import CaseAccessLevel, assert_transition, lock_case
from src.features.decision.schema import (
    CloseResponse,
    DecisionPreview,
    DecisionView,
    IssueDecisionRequest,
    ManagerQueueItem,
    ManagerQueueResponse,
    PrecedentRequest,
)
from src.models.case_drafts import CaseDraft
from src.models.cases import Case
from src.models.disciplinary_decisions import DisciplinaryDecision
from src.models.recommendations import Recommendation
from src.models.users import User

logger = logging.getLogger(__name__)

_COMPANY_SANCTIONS = frozenset({"WARNING", "REPRIMAND", "WAGE_POSTPONEMENT", "DEMOTION", "DISMISSAL"})


async def manager_queue(session: AsyncSession, actor: User) -> ManagerQueueResponse:
    """Approved cases waiting for the manager's final decision."""
    if actor.role != "MANAGER":
        raise AppError(403, "Chỉ quản lý xem hàng chờ duyệt cuối.", code="DECISION_NOT_ALLOWED")
    rows = list(
        (await session.scalars(select(Case).where(Case.status == "APPROVED").order_by(Case.updated_at.desc()))).all()
    )
    return ManagerQueueResponse(
        cases=[
            ManagerQueueItem(
                case_id=row.id,
                case_code=row.case_code,
                employee_code=row.employee_code,
                employee_name=row.employee_name,
                incident_date=row.incident_date,
                status=row.status,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
    )


async def decision_preview(session: AsyncSession, actor: User, case_id: UUID) -> DecisionPreview:
    """Show the approved decision draft. The sanction is the one legal already approved."""
    case, recommendation, draft = await _approved_bundle(session, actor, case_id, lock=False)
    return DecisionPreview(
        case_id=case.id,
        case_status=case.status,
        draft_id=draft.id,
        recommendation_id=recommendation.id,
        sanction_type=recommendation.sanction_type,
        decision_draft=draft.content,
        summary_hint=recommendation.rationale,
    )


async def issue_decision(
    session: AsyncSession,
    actor: User,
    case_id: UUID,
    payload: IssueDecisionRequest,
    idempotency_key: str | None,
) -> DecisionView:
    """Write the one decision for this case and move it to DECIDED."""
    route = f"POST /api/v1/cases/{case_id}/decisions"
    replay = await claim(
        session,
        actor_id=actor.id,
        route=route,
        key=idempotency_key,
        body_hash=request_hash(payload.model_dump(mode="json")),
    )
    if replay is not None:
        return DecisionView.model_validate(replay.body)
    if actor.role not in {"SIGNER", "MANAGER"}:
        raise AppError(403, "Chỉ quản lý hoặc người ký được duyệt lần cuối.", code="DECISION_NOT_ALLOWED")
    case, recommendation, draft = await _approved_bundle(session, actor, case_id, lock=True)
    existing = await session.scalar(select(DisciplinaryDecision.id).where(DisciplinaryDecision.case_id == case.id))
    if existing is not None:
        raise AppError(409, "Hồ sơ đã có quyết định.", code="DECISION_ALREADY_EXISTS")
    sanction = recommendation.sanction_type
    if sanction not in _COMPANY_SANCTIONS:
        raise AppError(409, "Đề xuất đã duyệt không có mức kỷ luật để ban hành.", code="DECISION_NOT_ALLOWED")
    assert_transition(case.status, "DECIDED")
    decision = DisciplinaryDecision(
        case_id=case.id,
        draft_id=draft.id,
        decision_code=payload.decision_code,
        sanction_type=sanction,
        summary=payload.summary,
        legal_basis=payload.legal_basis,
        issued_by=actor.id,
        issued_at=utc_now(),
    )
    session.add(decision)
    draft.status = "ISSUED"
    case.status = "DECIDED"
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(409, "Hồ sơ đã có quyết định.", code="DECISION_ALREADY_EXISTS") from exc
    await write_audit(
        session,
        case_id=case.id,
        actor_id=actor.id,
        actor_role=actor.role,
        action="DECISION_ISSUED",
        entity_type="disciplinary_decisions",
        entity_id=decision.id,
        before={"status": "APPROVED"},
        after={"status": "DECIDED", "decision_code": decision.decision_code, "sanction_type": sanction},
    )
    await notify(
        session,
        user_id=case.created_by,
        event="DECISION_ISSUED",
        title="Đã ban hành quyết định",
        body=f"Hồ sơ {case.case_code} đã có quyết định {decision.decision_code}.",
        case_id=case.id,
    )
    view = _decision_view(decision, case.status)
    await complete(
        session,
        actor_id=actor.id,
        route=route,
        key=idempotency_key,
        status_code=201,
        body=view.model_dump(mode="json"),
    )
    await session.commit()
    return view


async def mark_precedent(
    session: AsyncSession,
    actor: User,
    case_id: UUID,
    payload: PrecedentRequest,
    idempotency_key: str | None,
) -> DecisionView:
    """Embed an issued decision so a later case can cite it. Drafts cannot become precedent."""
    route = f"POST /api/v1/cases/{case_id}/decisions/precedent"
    summary = payload.precedent_summary.strip()
    if not summary:
        raise AppError(422, "Tóm tắt tiền lệ không được để trống.", code="UNPROCESSABLE")
    replay = await claim(
        session,
        actor_id=actor.id,
        route=route,
        key=idempotency_key,
        body_hash=request_hash({"precedent_summary": summary}),
    )
    if replay is not None:
        return DecisionView.model_validate(replay.body)
    if actor.role not in {"SIGNER", "ADMIN"}:
        raise AppError(403, "Chỉ người ký hoặc quản trị được đánh dấu tiền lệ.", code="FORBIDDEN")
    case = await lock_case(session, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    if actor.role != "ADMIN":
        await require_case_access(session, actor, case, CaseAccessLevel.VIEW)
    if case.status not in {"DECIDED", "CLOSED"}:
        raise AppError(409, "Chỉ quyết định đã ban hành mới thành tiền lệ.", code="DECISION_NOT_ALLOWED")
    decision = await session.scalar(select(DisciplinaryDecision).where(DisciplinaryDecision.case_id == case.id))
    if decision is None:
        raise AppError(409, "Hồ sơ chưa có quyết định đã ban hành.", code="DECISION_NOT_ALLOWED")
    vector = await _embed(summary)
    decision.is_precedent = True
    decision.precedent_summary = summary
    decision.embedding = vector
    await write_audit(
        session,
        case_id=case.id,
        actor_id=actor.id,
        actor_role=actor.role,
        action="PRECEDENT_CREATED",
        entity_type="disciplinary_decisions",
        entity_id=decision.id,
        after={"is_precedent": True},
    )
    view = _decision_view(decision, case.status)
    await complete(
        session,
        actor_id=actor.id,
        route=route,
        key=idempotency_key,
        status_code=200,
        body=view.model_dump(mode="json"),
    )
    await session.commit()
    return view


async def close_case(
    session: AsyncSession,
    actor: User,
    case_id: UUID,
    idempotency_key: str | None,
) -> CloseResponse:
    """Close a decided case. A case with no issued decision stays open."""
    route = f"POST /api/v1/cases/{case_id}/close"
    replay = await claim(
        session,
        actor_id=actor.id,
        route=route,
        key=idempotency_key,
        body_hash=request_hash({}),
    )
    if replay is not None:
        return CloseResponse.model_validate(replay.body)
    case = await lock_case(session, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    if actor.role == "ADMIN":
        pass
    elif actor.role in {"HR", "MANAGER"}:
        await require_case_access(session, actor, case, CaseAccessLevel.EDIT)
    elif actor.role == "SIGNER":
        await require_case_access(session, actor, case, CaseAccessLevel.VIEW)
    else:
        raise AppError(403, "Bạn không được đóng hồ sơ.", code="FORBIDDEN")
    decision = await session.scalar(select(DisciplinaryDecision.id).where(DisciplinaryDecision.case_id == case.id))
    if decision is None:
        raise AppError(409, "Chưa có quyết định nên chưa đóng hồ sơ.", code="DECISION_NOT_ALLOWED")
    assert_transition(case.status, "CLOSED")
    case.status = "CLOSED"
    await write_audit(
        session,
        case_id=case.id,
        actor_id=actor.id,
        actor_role=actor.role,
        action="CASE_CLOSED",
        entity_type="cases",
        entity_id=case.id,
        before={"status": "DECIDED"},
        after={"status": "CLOSED"},
    )
    await notify(
        session,
        user_id=case.created_by,
        event="CASE_CLOSED",
        title="Hồ sơ đã đóng",
        body=f"Hồ sơ {case.case_code} đã đóng.",
        case_id=case.id,
    )
    view = CloseResponse(case_id=case.id, status=case.status)
    await complete(
        session,
        actor_id=actor.id,
        route=route,
        key=idempotency_key,
        status_code=200,
        body=view.model_dump(mode="json"),
    )
    await session.commit()
    return view


async def _approved_bundle(
    session: AsyncSession,
    actor: User,
    case_id: UUID,
    *,
    lock: bool,
) -> tuple[Case, Recommendation, CaseDraft]:
    case = await lock_case(session, case_id) if lock else await session.get(Case, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    if actor.role not in {"SIGNER", "MANAGER"}:
        raise AppError(403, "Chỉ quản lý hoặc người ký được xem bản duyệt cuối.", code="DECISION_NOT_ALLOWED")
    if actor.role != "MANAGER":
        await require_case_access(session, actor, case, CaseAccessLevel.VIEW)
    if case.status != "APPROVED":
        raise AppError(409, "Hồ sơ chưa tới bước duyệt cuối.", code="DECISION_NOT_ALLOWED")
    recommendation = (
        await session.execute(
            select(Recommendation)
            .where(Recommendation.case_id == case.id, Recommendation.status == "APPROVED")
            .order_by(Recommendation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if recommendation is None or not recommendation.sanction_type:
        raise AppError(409, "Không có đề xuất đã duyệt để ban hành.", code="DECISION_NOT_ALLOWED")
    draft = (
        await session.execute(
            select(CaseDraft).where(
                CaseDraft.recommendation_id == recommendation.id,
                CaseDraft.draft_type == "DECISION",
                CaseDraft.status == "APPROVED",
            )
        )
    ).scalar_one_or_none()
    if draft is None:
        raise AppError(409, "Nháp quyết định chưa được duyệt.", code="DECISION_NOT_ALLOWED")
    return case, recommendation, draft


def _decision_view(decision: DisciplinaryDecision, status: str) -> DecisionView:
    return DecisionView(
        decision_id=decision.id,
        case_id=decision.case_id,
        decision_code=decision.decision_code,
        sanction_type=decision.sanction_type,
        summary=decision.summary,
        legal_basis=decision.legal_basis,
        issued_by=decision.issued_by,
        issued_at=decision.issued_at,
        case_status=status,
        is_precedent=bool(decision.is_precedent),
    )


async def _embed(text: str) -> list[float]:
    """Embed the precedent summary with mistral-embed. A missing key does not invent a vector."""

    def _call() -> list[float]:
        from src.services.embeddings_client import PURPOSE_QUERY, EmbeddingClient

        client = EmbeddingClient()
        vectors = client.embed([text], purpose=PURPOSE_QUERY, run_id="precedent")
        return vectors[0]

    try:
        return await asyncio.to_thread(_call)
    except Exception as exc:
        logger.exception("precedent embedding failed")
        raise AppError(503, "Chưa tạo được embedding tiền lệ.", code="EMBEDDING_UNAVAILABLE") from exc
