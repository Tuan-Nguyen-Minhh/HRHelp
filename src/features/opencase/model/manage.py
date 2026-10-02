"""List, correct, share, and reopen a case. Opening a case stays in ``cases.py``."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.access import require_case, require_case_access, require_mutable_case
from src.common.audit import write_audit
from src.common.errors import AppError
from src.common.idempotency import claim, complete, request_hash
from src.common.workflow import CaseAccessLevel, assert_transition, lock_case
from src.features.clarify.model.catalog import required_specs
from src.features.clarify.model.store import list_fact_rows
from src.features.opencase.model.cases import _view, active_conversation
from src.features.opencase.schema import (
    AccessGrantRequest,
    AccessGrantView,
    AccessListResponse,
    CaseListResponse,
    CasePatchRequest,
    CaseView,
    ReopenRequest,
    ReopenResponse,
)
from src.models.case_access import CaseAccess
from src.models.cases import Case
from src.models.recommendation_citations import RecommendationCitation
from src.models.recommendations import Recommendation
from src.models.users import User


async def list_cases(session: AsyncSession, actor: User) -> CaseListResponse:
    """Return cases the actor created or was granted, newest first."""
    from src.common.access import case_visibility

    stmt = select(Case).order_by(Case.created_at.desc())
    visible = case_visibility(actor)
    if visible is not None:
        stmt = stmt.where(visible)
    rows = list((await session.scalars(stmt)).all())
    views = []
    for case in rows:
        conversation = await active_conversation(session, case.id)
        views.append(_view(case, conversation.id if conversation else None))
    return CaseListResponse(cases=views)


async def patch_case(session: AsyncSession, actor: User, case_id: UUID, payload: CasePatchRequest) -> CaseView:
    """Correct header fields. Status is never taken from the client."""
    case = await require_mutable_case(session, case_id, actor)
    before = {
        "employee_code": case.employee_code,
        "employee_name": case.employee_name,
        "description": case.description,
        "incident_date": None if case.incident_date is None else case.incident_date.isoformat(),
        "family": case.family,
    }
    data = payload.model_dump(exclude_unset=True)
    for field in ("employee_code", "employee_name", "description", "incident_date", "family"):
        if field in data:
            setattr(case, field, data[field])
    await write_audit(
        session,
        case_id=case.id,
        actor_id=actor.id,
        actor_role=actor.role,
        action="CASE_UPDATED",
        entity_type="cases",
        entity_id=case.id,
        before=before,
        after={key: _plain(getattr(case, key)) for key in before},
    )
    await session.commit()
    conversation = await active_conversation(session, case.id)
    return _view(case, conversation.id if conversation else None)


async def grant_access(
    session: AsyncSession,
    actor: User,
    case_id: UUID,
    payload: AccessGrantRequest,
) -> AccessListResponse:
    """Give or remove one user's grant. The creator already has full access."""
    case = await session.get(Case, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    if actor.role != "ADMIN" and case.created_by != actor.id:
        raise AppError(403, "Chỉ người tạo hồ sơ hoặc quản trị được cấp quyền.", code="FORBIDDEN")
    target = await session.get(User, payload.user_id)
    if target is None or not target.is_active or target.deleted_at is not None:
        raise AppError(404, "Không tìm thấy người được cấp quyền.", code="NOT_FOUND")
    existing = await session.scalar(
        select(CaseAccess).where(CaseAccess.case_id == case.id, CaseAccess.user_id == target.id)
    )
    if payload.revoke:
        if existing is not None:
            await session.delete(existing)
            await write_audit(
                session,
                case_id=case.id,
                actor_id=actor.id,
                actor_role=actor.role,
                action="ACCESS_REVOKED",
                entity_type="case_access",
                entity_id=existing.id,
                before={"user_id": str(target.id), "access_level": existing.access_level},
            )
        await session.commit()
        return await list_access(session, actor, case.id)
    if payload.access_level is None:
        raise AppError(422, "Thiếu mức truy cập.", code="UNPROCESSABLE")
    if target.role == "LEGAL" and payload.access_level == "EDIT":
        raise AppError(403, "Pháp chế không được sửa tình tiết.", code="FORBIDDEN")
    if target.role == "SIGNER" and payload.access_level == "EDIT":
        raise AppError(403, "Người ký không được sửa đề xuất hoặc tình tiết.", code="FORBIDDEN")
    if existing is None:
        existing = CaseAccess(
            case_id=case.id, user_id=target.id, access_level=payload.access_level, granted_by=actor.id
        )
        session.add(existing)
    else:
        existing.access_level = payload.access_level
        existing.granted_by = actor.id
    await session.flush()
    await write_audit(
        session,
        case_id=case.id,
        actor_id=actor.id,
        actor_role=actor.role,
        action="ACCESS_GRANTED",
        entity_type="case_access",
        entity_id=existing.id,
        after={"user_id": str(target.id), "access_level": payload.access_level},
    )
    await session.commit()
    return await list_access(session, actor, case.id)


async def list_access(session: AsyncSession, actor: User, case_id: UUID) -> AccessListResponse:
    """List grants. Viewing the list requires view access."""
    case = await require_case(session, case_id, actor)
    rows = list(
        (
            await session.scalars(
                select(CaseAccess).where(CaseAccess.case_id == case.id).order_by(CaseAccess.created_at.asc())
            )
        ).all()
    )
    return AccessListResponse(
        case_id=case.id,
        grants=[
            AccessGrantView(
                user_id=row.user_id,
                access_level=row.access_level,
                granted_by=row.granted_by,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )


async def reopen_case(
    session: AsyncSession,
    actor: User,
    case_id: UUID,
    payload: ReopenRequest,
    idempotency_key: str | None,
) -> ReopenResponse:
    """Return a rejected case to HR. Keeping the report copies it into a new draft."""
    route = f"POST /api/v1/cases/{case_id}/reopen"
    replay = await claim(
        session,
        actor_id=actor.id,
        route=route,
        key=idempotency_key,
        body_hash=request_hash(payload.model_dump(mode="json")),
    )
    if replay is not None:
        return ReopenResponse.model_validate(replay.body)
    case = await lock_case(session, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    if actor.role not in {"HR", "MANAGER"}:
        raise AppError(403, "Chỉ HR hoặc quản lý được mở lại hồ sơ.", code="FORBIDDEN")
    await require_case_access(session, actor, case, CaseAccessLevel.EDIT)
    if case.status != "REJECTED":
        raise AppError(409, "Chỉ hồ sơ bị từ chối mới mở lại.", code="INVALID_CASE_TRANSITION")
    target = payload.target or await _reopen_target(session, case)
    assert_transition(case.status, target)
    case.status = target
    if target == "ANALYZED":
        await _copy_rejected_report(session, case)
    await write_audit(
        session,
        case_id=case.id,
        actor_id=actor.id,
        actor_role=actor.role,
        action="CASE_REOPENED",
        entity_type="cases",
        entity_id=case.id,
        before={"status": "REJECTED"},
        after={"status": target},
    )
    view = ReopenResponse(case_id=case.id, status=case.status)
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


async def _copy_rejected_report(session: AsyncSession, case: Case) -> None:
    """Copy the rejected report into a new draft so HR can send it again.

    The old review stays on the rejected row. A new legal review needs a new recommendation.
    """
    current = await session.scalar(
        select(Recommendation)
        .where(Recommendation.case_id == case.id, Recommendation.status == "REJECTED")
        .order_by(Recommendation.created_at.desc())
        .limit(1)
    )
    if current is None:
        return
    current.status = "SUPERSEDED"
    copy = Recommendation(
        id=uuid4(),
        case_id=case.id,
        agent_run_id=current.agent_run_id,
        recommendation=current.recommendation,
        rationale=current.rationale,
        sanction_type=current.sanction_type,
        process_steps=current.process_steps,
        risk_level=current.risk_level,
        status="DRAFT",
    )
    session.add(copy)
    citations = list(
        (
            await session.scalars(
                select(RecommendationCitation).where(RecommendationCitation.recommendation_id == current.id)
            )
        ).all()
    )
    for item in citations:
        session.add(
            RecommendationCitation(
                id=uuid4(),
                recommendation_id=copy.id,
                chunk_id=item.chunk_id,
                quote=item.quote,
                article=item.article,
                clause=item.clause,
                point=item.point,
                score=item.score,
            )
        )
    await session.flush()


async def _reopen_target(session: AsyncSession, case: Case) -> str:
    """ANALYZED when every required fact is confirmed. Otherwise HR must fill the gaps."""
    family = case.family or "GENERAL"
    rows = {row.fact_key: row for row in await list_fact_rows(session, case.id)}
    for spec in required_specs(family):
        row = rows.get(spec.key)
        if row is None or not row.confirmed or not row.fact_value:
            return "NEED_INFO"
    return "ANALYZED"


def _plain(value: object) -> object:
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return value
