"""Approve or reject a ticket. Sanction, facts, and citations are not writable here."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.access import require_case_access
from src.common.audit import write_audit
from src.common.errors import AppError
from src.common.idempotency import claim, complete, request_hash
from src.common.notify import notify, notify_managers
from src.common.workflow import CaseAccessLevel, assert_transition, lock_case
from src.features.answer.model.answers import load_stored
from src.features.legal_review.schema import QueueItem, QueueResponse, ReviewPack, ReviewRequest, ReviewView
from src.models.case_drafts import CaseDraft
from src.models.cases import Case
from src.models.recommendations import Recommendation
from src.models.reviews import Review
from src.models.users import User


async def review_queue(session: AsyncSession, actor: User) -> QueueResponse:
    """Every ticket HR sent. The legal page is the LEGAL role, not a per-user grant."""
    _require_legal(actor)
    stmt = select(Case).where(Case.status == "PENDING_LEGAL").order_by(Case.updated_at.desc())
    rows = list((await session.scalars(stmt)).all())
    return QueueResponse(
        reviews=[
            QueueItem(
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


async def review_pack(session: AsyncSession, actor: User, case_id: UUID) -> ReviewPack:
    """Read the stored assessment and drafts. This does not run an agent."""
    _require_legal(actor)
    case = await session.get(Case, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    view = await load_stored(session, case)
    if view is None:
        raise AppError(404, "Hồ sơ chưa có báo cáo.", code="NOT_FOUND")
    return ReviewPack(
        case_id=case.id,
        case_code=case.case_code,
        status=case.status,
        employee_code=case.employee_code,
        employee_name=case.employee_name,
        incident_date=case.incident_date,
        description=case.description,
        answer=view,
    )


async def submit_review(
    session: AsyncSession,
    actor: User,
    case_id: UUID,
    payload: ReviewRequest,
    idempotency_key: str | None,
) -> ReviewView:
    """Record the human decision and move the case, recommendation, and drafts together."""
    route = f"POST /api/v1/cases/{case_id}/reviews"
    replay = await claim(
        session,
        actor_id=actor.id,
        route=route,
        key=idempotency_key,
        body_hash=request_hash(payload.model_dump(mode="json")),
    )
    if replay is not None:
        return ReviewView.model_validate(replay.body)
    _require_legal(actor)
    case = await lock_case(session, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    if case.status != "PENDING_LEGAL":
        raise AppError(409, "Hồ sơ không còn trong hàng chờ pháp chế.", code="REVIEW_NOT_ALLOWED")
    recommendation = await _pending_recommendation(session, case.id)
    if recommendation is None:
        raise AppError(409, "Không có đề xuất đang chờ duyệt.", code="REVIEW_NOT_ALLOWED")
    existing = await session.scalar(select(Review.id).where(Review.recommendation_id == recommendation.id))
    if existing is not None:
        raise AppError(409, "Đề xuất này đã được duyệt.", code="REVIEW_NOT_ALLOWED")
    drafts = list(
        (await session.scalars(select(CaseDraft).where(CaseDraft.recommendation_id == recommendation.id))).all()
    )
    ticket = next((item for item in drafts if item.draft_type == "TICKET"), None)
    approved = payload.decision == "APPROVE"
    target = "APPROVED" if approved else "REJECTED"
    assert_transition(case.status, target)
    review = Review(
        case_id=case.id,
        recommendation_id=recommendation.id,
        draft_id=None if ticket is None else ticket.id,
        reviewer_id=actor.id,
        decision=payload.decision,
        comment=payload.comment,
    )
    session.add(review)
    recommendation.status = target
    for draft in drafts:
        draft.status = target
    case.status = target
    await session.flush()
    action = "LEGAL_APPROVED" if approved else "LEGAL_REJECTED"
    await write_audit(
        session,
        case_id=case.id,
        actor_id=actor.id,
        actor_role=actor.role,
        action=action,
        entity_type="reviews",
        entity_id=review.id,
        before={"status": "PENDING_LEGAL"},
        after={"status": target, "decision": payload.decision},
        metadata={"comment": payload.comment} if payload.comment else None,
    )
    await notify(
        session,
        user_id=case.created_by,
        event=action,
        title="Pháp chế đã duyệt" if approved else "Pháp chế yêu cầu xử lý lại",
        body=(
            f"Hồ sơ {case.case_code} đã duyệt. Quản lý duyệt lần cuối."
            if approved
            else f"Hồ sơ {case.case_code} cần xử lý lại. {payload.comment or ''}".strip()
        ),
        case_id=case.id,
    )
    if approved:
        await notify_managers(
            session,
            case_id=case.id,
            event="MANAGER_REVIEW_REQUESTED",
            title="Hồ sơ chờ duyệt cuối",
            body=f"Pháp chế đã duyệt hồ sơ {case.case_code}. Quản lý duyệt lần cuối.",
        )
    view = ReviewView(
        review_id=review.id,
        case_id=case.id,
        decision=review.decision,
        comment=review.comment,
        case_status=case.status,
    )
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


async def latest_review(session: AsyncSession, actor: User, case_id: UUID) -> ReviewView:
    """The last legal note, so HR can see a request to rework."""
    case = await session.get(Case, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    await require_case_access(session, actor, case, CaseAccessLevel.VIEW)
    review = await session.scalar(
        select(Review).where(Review.case_id == case.id).order_by(Review.decided_at.desc()).limit(1)
    )
    if review is None:
        raise AppError(404, "Hồ sơ chưa có kết luận pháp chế.", code="NOT_FOUND")
    return ReviewView(
        review_id=review.id,
        case_id=case.id,
        decision=review.decision,
        comment=review.comment,
        case_status=case.status,
    )


def _require_legal(actor: User) -> None:
    if actor.role != "LEGAL":
        raise AppError(403, "Chỉ pháp chế được duyệt phiếu.", code="REVIEW_NOT_ALLOWED")


async def _pending_recommendation(session: AsyncSession, case_id: UUID) -> Recommendation | None:
    stmt = (
        select(Recommendation)
        .where(Recommendation.case_id == case_id, Recommendation.status == "PENDING_REVIEW")
        .order_by(Recommendation.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    return (await session.execute(stmt)).scalar_one_or_none()
