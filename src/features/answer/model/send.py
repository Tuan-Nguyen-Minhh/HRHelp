"""Show the legal ticket before HR chooses a recipient and sends it.

Feature 6 has already stored the draft. This module does not choose a sanction.
The dispatch graph still reads only ``ProposalHandoff``.
"""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.handoff import CaseHandoff
from src.agents.runs import finish_run, start_run
from src.common.access import require_case_access
from src.common.audit import write_audit
from src.common.clock import utc_now
from src.common.errors import AppError
from src.common.idempotency import abandon, claim, complete, request_hash
from src.common.notify import notify_legal, notify_managers
from src.common.workflow import CaseAccessLevel, lock_case
from src.features.answer.model.dispatch import (
    DispatchResult,
    build_dispatch_agent,
    drafts_for_review,
    hold_fields,
    ready_to_dispatch,
)
from src.features.answer.model.proposal import ProposalHandoff, close_proposal
from src.features.answer.model.release import save_direct_approval, save_submission
from src.features.answer.schema import AnswerView, DraftView
from src.features.answer.schema.present import with_packet
from src.features.clarify.model.catalog import fact_lines
from src.features.clarify.model.store import NewMessage, add_message, list_fact_rows
from src.features.opencase.model.cases import active_conversation
from src.models.cases import Case
from src.models.recommendations import Recommendation
from src.models.users import User

_ASK = (
    "Báo cáo đã lập. Hãy xem phiếu chuyển pháp chế trước. "
    "Bạn có muốn đẩy báo cáo này cho pháp chế không? Nếu có, chọn email pháp chế sẽ nhận phiếu."
)


async def list_legal_officers(session: AsyncSession) -> list[User]:
    """Active pháp chế accounts. HR addresses one of them by email."""
    stmt = (
        select(User)
        .where(User.role == "LEGAL", User.is_active.is_(True), User.deleted_at.is_(None))
        .order_by(User.email)
    )
    return list((await session.scalars(stmt)).all())


async def find_legal_officer(session: AsyncSession, email: str) -> User | None:
    """The active pháp chế account for this email, if one exists."""
    stmt = select(User).where(
        User.email == email.casefold(),
        User.role == "LEGAL",
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    )
    return await session.scalar(stmt)


def ask_to_send() -> str:
    """The question HR sees after feature 6, before any legal draft is stored."""
    return _ASK


def proposal_from_parts(
    case: Case,
    view: AnswerView,
    facts: dict[str, str],
    *,
    legal_code: str | None,
) -> ProposalHandoff:
    """Rebuild the feature 7 message from the stored proposal. The level stays as stored."""
    if case.incident_date is None:
        raise AppError(422, "Hồ sơ chưa có ngày xảy ra việc nên chưa đẩy phiếu.")
    family = _family(facts)
    message = CaseHandoff(
        case_id=case.id,
        incident_date=case.incident_date,
        employee_name=case.employee_name,
        description=case.description or "",
        family=family,
        facts=dict(facts),
        fact_lines=fact_lines(family, facts),
        missing_internal_rule=view.missing_internal_rule,
        agent_run_id=view.agent_run_id or uuid4(),
    )
    return close_proposal(message, view, employee_code=case.employee_code, legal_code=legal_code)


async def with_preview(session: AsyncSession, case: Case, view: AnswerView) -> AnswerView:
    """Attach the review minutes, and the legal packet when the gate would submit."""
    if view.drafts or case.status != "ANALYZED" or view.agent_run_id is None or case.incident_date is None:
        return view
    proposal = proposal_from_parts(case, view, await _facts(session, case.id), legal_code=None)
    state = await build_dispatch_agent().ainvoke({"proposal": proposal})
    result = state.get("result")
    if not isinstance(result, DispatchResult):
        return view
    if result.disposition == "SUBMIT":
        chosen = list(result.drafts)
    elif result.disposition == "HOLD" and await _assessment_confirmed(session, case.id):
        chosen = list(drafts_for_review(proposal).drafts)
    elif result.disposition == "HOLD":
        chosen = [item for item in result.drafts if item.draft_type == "MINUTES"]
    else:
        return view
    if not chosen:
        return view
    drafts = [
        DraftView(
            draft_id=uuid4(),
            draft_type=item.draft_type,
            title=item.title,
            content=item.content,
            status="PREVIEW",
        )
        for item in chosen
    ]
    return with_packet(view, drafts)


async def send_ticket(
    session: AsyncSession,
    actor: User,
    case_id: UUID,
    legal_code: str,
    idempotency_key: str | None = None,
) -> AnswerView:
    """Store the four drafts for the legal code HR just confirmed."""
    route = f"POST /api/v1/cases/{case_id}/ticket"
    replay = await claim(
        session,
        actor_id=actor.id,
        route=route,
        key=idempotency_key,
        body_hash=request_hash({"legal_code": legal_code}),
    )
    if replay is not None:
        return AnswerView.model_validate(replay.body)
    case = await lock_case(session, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    if actor.role not in {"HR", "MANAGER"}:
        raise AppError(403, "Chỉ HR hoặc quản lý được đẩy phiếu.", code="FORBIDDEN")
    officer = await find_legal_officer(session, legal_code)
    if officer is None:
        raise AppError(404, "Không có tài khoản pháp chế với email này.", code="LEGAL_OFFICER_NOT_FOUND")
    legal_code = officer.email
    await require_case_access(session, actor, case, CaseAccessLevel.EDIT)
    if case.status == "PENDING_LEGAL":
        raise AppError(409, "Phiếu đã ở hàng chờ pháp chế.", code="TICKET_ALREADY_SUBMITTED")
    if case.status != "ANALYZED":
        raise AppError(409, "Hồ sơ không còn ở bước xem báo cáo nên không đẩy phiếu.", code="CASE_NOT_EDITABLE")
    from src.features.answer.model.answers import load_stored

    view = await load_stored(session, case)
    if view is None:
        raise AppError(404, "Hồ sơ chưa có báo cáo để đẩy.")
    current = await session.get(Recommendation, view.recommendation_id)
    if not ready_to_dispatch(case.status, None if current is None else current.status):
        raise AppError(409, "Đề xuất không còn bản nháp nên không đẩy phiếu.")
    code = hold_fields(view.sanction_type, view.risk_level, view.missing_internal_rule, view.process_steps)
    if code is not None and (code == "TERMINATION" or not await _assessment_confirmed(session, case.id)):
        raise AppError(409, "Báo cáo đang được giữ lại, chưa đẩy pháp chế.", code="DISPATCH_HOLD")
    conversation = await active_conversation(session, case.id)
    if conversation is None:
        raise AppError(409, "Hồ sơ chưa có hội thoại đang mở.")
    proposal = proposal_from_parts(case, view, await _facts(session, case.id), legal_code=legal_code)
    note = await add_message(
        session,
        NewMessage(conversation.id, "USER", f"Đẩy phiếu cho pháp chế {legal_code}.", {"kind": "legal_send"}),
    )
    run = await start_run(session, conversation.id, note.id, "hr-help-dispatch")
    if code is None:
        try:
            state = await build_dispatch_agent().ainvoke({"proposal": proposal})
        except TypeError as exc:
            _fail(run, str(exc))
            await abandon(session, actor_id=actor.id, route=route, key=idempotency_key)
            await session.commit()
            raise AppError(409, "Chưa đẩy được phiếu. Báo cáo vẫn để xem.") from exc
        result = state.get("result")
        if not isinstance(result, DispatchResult) or result.disposition != "SUBMIT":
            _fail(run, "Dispatch graph không trả phiếu để gửi.")
            await abandon(session, actor_id=actor.id, route=route, key=idempotency_key)
            await session.commit()
            raise AppError(409, "Báo cáo chưa đủ căn cứ để đẩy pháp chế.", code="DISPATCH_HOLD")
    else:
        result = drafts_for_review(proposal)
    try:
        await save_submission(session, case, proposal, result)
    except Exception as exc:
        _fail(run, str(exc))
        await abandon(session, actor_id=actor.id, route=route, key=idempotency_key)
        await session.commit()
        raise AppError(409, "Chưa đẩy được phiếu. Báo cáo vẫn để xem.") from exc
    sent = await add_message(
        session,
        NewMessage(
            conversation.id,
            "ASSISTANT",
            f"Đã đẩy phiếu cho pháp chế {legal_code}. Phiếu đang ở hàng chờ.",
            {"kind": "dispatch_submit", "legal_code": legal_code},
        ),
    )
    finish_run(run, sent.id)
    await write_audit(
        session,
        case_id=case.id,
        actor_id=actor.id,
        actor_role=actor.role,
        action="LEGAL_TICKET_SUBMITTED",
        entity_type="cases",
        entity_id=case.id,
        before={"status": "ANALYZED"},
        after={"status": "PENDING_LEGAL", "legal_code": legal_code},
    )
    await notify_legal(
        session,
        case_id=case.id,
        event="LEGAL_TICKET_SUBMITTED",
        title="Có phiếu chờ duyệt",
        body=f"Hồ sơ {case.case_code} đã được chuyển pháp chế {legal_code}.",
    )
    fresh = await load_stored(session, case)
    result = fresh if fresh is not None else view
    await complete(
        session,
        actor_id=actor.id,
        route=route,
        key=idempotency_key,
        status_code=200,
        body=result.model_dump(mode="json"),
    )
    await session.commit()
    return result


async def escalate_to_manager(
    session: AsyncSession,
    actor: User,
    case_id: UUID,
    idempotency_key: str | None = None,
) -> AnswerView:
    """HR skips legal and places the stored proposal on the manager queue."""
    route = f"POST /api/v1/cases/{case_id}/escalate"
    replay = await claim(
        session,
        actor_id=actor.id,
        route=route,
        key=idempotency_key,
        body_hash=request_hash({}),
    )
    if replay is not None:
        return AnswerView.model_validate(replay.body)
    case = await lock_case(session, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    if actor.role != "HR":
        raise AppError(403, "Chỉ HR được chuyển thẳng cho quản lý.", code="FORBIDDEN")
    await require_case_access(session, actor, case, CaseAccessLevel.EDIT)
    if case.status != "ANALYZED":
        raise AppError(409, "Hồ sơ không còn ở bước xem báo cáo nên không chuyển quản lý.", code="CASE_NOT_EDITABLE")
    from src.features.answer.model.answers import load_stored

    view = await load_stored(session, case)
    if view is None:
        raise AppError(404, "Hồ sơ chưa có báo cáo để chuyển.")
    current = await session.get(Recommendation, view.recommendation_id)
    if not ready_to_dispatch(case.status, None if current is None else current.status):
        raise AppError(409, "Đề xuất không còn bản nháp nên không chuyển quản lý.")
    code = hold_fields(view.sanction_type, view.risk_level, view.missing_internal_rule, view.process_steps)
    if code is not None and (code == "TERMINATION" or not await _assessment_confirmed(session, case.id)):
        raise AppError(409, "Báo cáo đang được giữ lại, chưa chuyển quản lý.", code="DISPATCH_HOLD")
    conversation = await active_conversation(session, case.id)
    if conversation is None:
        raise AppError(409, "Hồ sơ chưa có hội thoại đang mở.")
    proposal = proposal_from_parts(case, view, await _facts(session, case.id), legal_code=None)
    note = await add_message(
        session,
        NewMessage(
            conversation.id, "USER", "HR xử lý luôn và chuyển quản lý duyệt lần cuối.", {"kind": "manager_escalate"}
        ),
    )
    run = await start_run(session, conversation.id, note.id, "hr-help-dispatch")
    if code is None:
        try:
            state = await build_dispatch_agent().ainvoke({"proposal": proposal})
        except TypeError as exc:
            _fail(run, str(exc))
            await abandon(session, actor_id=actor.id, route=route, key=idempotency_key)
            await session.commit()
            raise AppError(409, "Chưa chuyển được quản lý. Báo cáo vẫn để xem.") from exc
        result = state.get("result")
        if not isinstance(result, DispatchResult) or result.disposition != "SUBMIT":
            _fail(run, "Dispatch graph không trả phiếu để chuyển.")
            await abandon(session, actor_id=actor.id, route=route, key=idempotency_key)
            await session.commit()
            raise AppError(409, "Báo cáo chưa đủ căn cứ để chuyển quản lý.", code="DISPATCH_HOLD")
    else:
        result = drafts_for_review(proposal)
    try:
        await save_direct_approval(session, case, proposal, result)
    except Exception as exc:
        _fail(run, str(exc))
        await abandon(session, actor_id=actor.id, route=route, key=idempotency_key)
        await session.commit()
        raise AppError(409, "Chưa chuyển được quản lý. Báo cáo vẫn để xem.") from exc
    sent = await add_message(
        session,
        NewMessage(
            conversation.id,
            "ASSISTANT",
            "HR đã chuyển hồ sơ cho quản lý duyệt lần cuối. Pháp chế không nhận phiếu này.",
            {"kind": "manager_escalate"},
        ),
    )
    finish_run(run, sent.id)
    await write_audit(
        session,
        case_id=case.id,
        actor_id=actor.id,
        actor_role=actor.role,
        action="HR_ESCALATED",
        entity_type="cases",
        entity_id=case.id,
        before={"status": "ANALYZED"},
        after={"status": "APPROVED", "path": "HR_DIRECT"},
    )
    await notify_managers(
        session,
        case_id=case.id,
        event="MANAGER_REVIEW_REQUESTED",
        title="Hồ sơ chờ duyệt cuối",
        body=f"HR chuyển thẳng hồ sơ {case.case_code}. Quản lý duyệt lần cuối.",
    )
    fresh = await load_stored(session, case)
    stored = fresh if fresh is not None else view
    await complete(
        session,
        actor_id=actor.id,
        route=route,
        key=idempotency_key,
        status_code=200,
        body=stored.model_dump(mode="json"),
    )
    await session.commit()
    return stored


async def _assessment_confirmed(session: AsyncSession | None, case_id: UUID) -> bool:
    """True when the current assessment version is the one HR confirmed."""
    if session is None:
        return False
    from src.features.assessment.repository import current_version, get_report

    report = await get_report(session, case_id)
    if report is None or report.status != "CONFIRMED":
        return False
    version = await current_version(session, report)
    return version is not None and version.status == "CONFIRMED"


async def _facts(session: AsyncSession, case_id: UUID) -> dict[str, str]:
    rows = await list_fact_rows(session, case_id)
    return {row.fact_key: row.fact_value for row in rows if row.confirmed and row.fact_value}


def _family(facts: dict[str, str]) -> str:
    if "absence_days" in facts or "notice_form" in facts:
        return "UNAUTHORIZED_ABSENCE"
    if "late_days" in facts:
        return "LATE"
    return "GENERAL"


def _fail(run, error: str) -> None:
    run.status = "FAILED"
    run.error = error[:2000]
    run.completed_at = utc_now()
