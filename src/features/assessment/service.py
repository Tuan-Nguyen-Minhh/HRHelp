"""Load, draft, edit, and confirm an assessment. This module does not send a ticket."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.common.access import MUTABLE_STATUSES, require_case_access
from src.common.audit import write_audit
from src.common.clock import utc_now, vietnam_date
from src.common.errors import AppError
from src.common.minutes_profile import minutes_profile
from src.common.workflow import CaseAccessLevel, assert_transition, lock_case
from src.features.answer.model.answers import load, load_stored
from src.features.answer.schema import AnswerView
from src.features.assessment.agent import ComposeInput, FactInput, compose
from src.features.assessment.repository import append_version, current_version, get_report
from src.features.assessment.schemas import (
    AssessmentMetadata,
    AssessmentPatch,
    AssessmentView,
    ConfirmedFact,
    FormStatus,
    Permissions,
    Sections,
)
from src.features.assessment.validator import validate_sections
from src.features.clarify.model.catalog import OPTIONAL_FACT_KEYS, fact_label, required_specs, resolved_family
from src.features.clarify.model.store import list_fact_rows
from src.features.opencase.model.manage import _copy_rejected_report
from src.models.assessment_reports import AssessmentReport, AssessmentVersion
from src.models.cases import Case
from src.models.users import User

_PROMPT = "assessment-form-v1"
_OPTIONAL_LABELS = {"prior_sanction_count": "Số lần đã xử lý trước đây"}


async def get_assessment(session: AsyncSession, actor: User, case_id: UUID) -> AssessmentView:
    case = await _case(session, actor, case_id, CaseAccessLevel.VIEW)
    report = await get_report(session, case.id)
    if report is None:
        raise AppError(404, "Hồ sơ chưa có biên bản đánh giá.", code="NOT_FOUND")
    version = await current_version(session, report)
    if version is None:
        raise AppError(404, "Hồ sơ chưa có biên bản đánh giá.", code="NOT_FOUND")
    if _can_refresh(actor, case, version) and _catalog_mismatch(case, _saved(version)[0]):
        # A draft that asks for the wrong fact set cannot be confirmed. Rebuild it once.
        try:
            return await generate_assessment(session, actor, case_id)
        except AppError:
            return await _present(session, actor, case, report, version)
    return await _present(session, actor, case, report, version)


async def generate_assessment(
    session: AsyncSession, actor: User, case_id: UUID, *, commit: bool = True
) -> AssessmentView:
    """Create the next draft from the stored recommendation. The model does not confirm it."""
    case = await _editable(session, actor, case_id)
    sections, sources = await _compose_case(session, case)
    report = await get_report(session, case.id)
    if report is not None:
        previous = await current_version(session, report)
        if previous is not None:
            old_sections, old_sources = _saved(previous)
            sections, sources = _carry(sections, sources, old_sections, old_sources)
    return await _store_new(session, actor, case, sections, sources, "AI", report, commit=commit)


async def ensure_assessment(session: AsyncSession, actor: User, case_id: UUID) -> AssessmentView:
    """Save a chat-requested draft in the caller's transaction; preserve HR edits."""
    case = await _editable(session, actor, case_id)
    report = await get_report(session, case.id)
    if report is not None:
        version = await current_version(session, report)
        answer = await load(session, case)
        if version is not None and (
            version.status == "CONFIRMED"
            or version.source == "HR"
            or (answer is not None and report.recommendation_id == answer.recommendation_id)
        ):
            return await _present(session, actor, case, report, version)
    return await generate_assessment(session, actor, case.id, commit=False)


async def save_assessment(
    session: AsyncSession,
    actor: User,
    case_id: UUID,
    patch: AssessmentPatch,
) -> AssessmentView:
    case = await _editable(session, actor, case_id)
    report, version = await _open(session, case.id)
    if version.status == "CONFIRMED":
        raise AppError(
            409,
            "Biên bản đã xác nhận. Hãy lập lại phân tích nếu cần bản mới.",
            code="ASSESSMENT_CONFIRMED",
        )
    sections, sources = _saved(version)
    sections, sources = _merge(sections, sources, patch)
    await _apply_case_edits(session, actor, case, patch)
    return await _store_new(session, actor, case, sections, sources, "HR", report)


async def confirm_assessment(session: AsyncSession, actor: User, case_id: UUID) -> AssessmentView:
    """HR confirms the current draft. A blocking gap refuses. No ticket is sent."""
    case = await _editable(session, actor, case_id)
    report, version = await _open(session, case.id)
    if version.status == "CONFIRMED":
        return await _present(session, actor, case, report, version)
    sections, sources = _saved(version)
    validation = await _checked(session, case, sections)
    if not validation.is_valid:
        raise AppError(
            409,
            "Biên bản còn thông tin bắt buộc chưa đủ.",
            code="ASSESSMENT_BLOCKED",
            details={"blocking_errors": validation.blocking_errors},
        )
    return await _store_new(session, actor, case, sections, sources, version.source, report, status="CONFIRMED")


async def reanalyze_assessment(session: AsyncSession, actor: User, case_id: UUID) -> AssessmentView:
    """Open the saved minutes as a new HR draft, preserving the submitted version."""
    case = await lock_case(session, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    await require_case_access(session, actor, case, CaseAccessLevel.EDIT)
    if actor.role not in {"HR", "MANAGER"}:
        raise AppError(403, "Chỉ HR được sửa biên bản.", code="FORBIDDEN")
    if case.status not in MUTABLE_STATUSES:
        raise AppError(409, "Hồ sơ không còn ở bước sửa biên bản.", code="CASE_NOT_EDITABLE")
    report, version = await _open(session, case.id)
    previous_status = case.status
    if case.status == "REJECTED":
        assert_transition(case.status, "ANALYZED")
        await _copy_rejected_report(session, case)
        case.status = "ANALYZED"
    sections, sources = _saved(version)
    sections = sections.model_copy(
        update={
            "case_information": sections.case_information.model_copy(update={"case_status": case.status}),
        }
    )
    answer = await load_stored(session, case)
    sections = _align_saved_citations(sections, answer)
    await write_audit(
        session,
        case_id=case.id,
        actor_id=actor.id,
        actor_role=actor.role,
        action="ASSESSMENT_REVISED",
        entity_type="assessment_reports",
        entity_id=report.id,
        before={"status": previous_status, "version": version.version},
        after={"status": case.status, "source": "HR", "version": version.version + 1},
    )
    return await _store_new(session, actor, case, sections, sources, "HR", report)


def _align_saved_citations(sections: Sections, answer: AnswerView | None) -> Sections:
    """Retain snapshot quotes whose original chunk was removed; never invent a source."""
    if answer is None:
        return sections
    rows = [*answer.legal_basis, *answer.internal_rule, *answer.precedent, *answer.inspection_risk]

    def signature(item):
        return (" ".join(item.quote.split()), item.article, item.clause, item.point)

    archived = {signature(item) for item in rows if item.chunk_id is None}
    allowed = _stored_chunk_ids(answer)

    def align(card):
        if card.chunk_id is not None and str(card.chunk_id) not in allowed and signature(card) in archived:
            return card.model_copy(update={"chunk_id": None})
        return card

    return sections.model_copy(
        update={
            "citations": [align(card) for card in sections.citations],
            "evidence_reviewed": [align(card) for card in sections.evidence_reviewed],
        }
    )


async def _compose_case(session: AsyncSession, case: Case) -> tuple[Sections, dict[str, str]]:
    answer = await load(session, case)
    if answer is None:
        raise AppError(409, "Chưa có báo cáo đã lưu để lập biên bản.", code="ASSESSMENT_NOT_READY")
    rows = {row.fact_key: row for row in await list_fact_rows(session, case.id)}
    family = resolved_family(case.description or "", case.family)
    if case.family != family:
        case.family = family
    specs = list(required_specs(family))
    facts = []
    for spec in specs:
        row = rows.get(spec.key)
        facts.append(
            FactInput(
                key=spec.key,
                label=spec.label,
                value=None if row is None else row.fact_value,
                confirmed=bool(row and row.confirmed and row.fact_value),
                required=True,
            )
        )
    used = {spec.key for spec in specs}
    for key, row in rows.items():
        if key in used or key in OPTIONAL_FACT_KEYS or not (row.fact_value and row.fact_value.strip()):
            continue
        facts.append(
            FactInput(
                key=key,
                label=fact_label(key),
                value=row.fact_value,
                confirmed=bool(row.confirmed),
                required=False,
            )
        )
    for key in OPTIONAL_FACT_KEYS:
        row = rows.get(key)
        if row is None:
            continue
        facts.append(
            FactInput(
                key=key,
                label=_OPTIONAL_LABELS.get(key, key),
                value=row.fact_value,
                confirmed=bool(row.confirmed),
                required=False,
            )
        )
    sections, sources = compose(
        ComposeInput(
            case_code=case.case_code,
            case_status=case.status,
            family=family,
            incident_date=case.incident_date,
            description=case.description or "",
            employee_code=case.employee_code,
            employee_name=case.employee_name,
            facts=tuple(facts),
            answer=answer,
        )
    )
    return sections, sources


async def _store_new(
    session: AsyncSession,
    actor: User,
    case: Case,
    sections: Sections,
    sources: dict[str, str],
    source: str,
    report: AssessmentReport | None = None,
    status: str = "DRAFT",
    *,
    commit: bool = True,
) -> AssessmentView:
    if report is None:
        report = await get_report(session, case.id)
    if report is None:
        answer = await load(session, case)
        report = AssessmentReport(
            id=uuid4(),
            case_id=case.id,
            recommendation_id=None if answer is None else answer.recommendation_id,
            status="DRAFT",
            current_version=0,
        )
        session.add(report)
        await session.flush()
    else:
        answer = await load(session, case)
        if answer is not None:
            report.recommendation_id = answer.recommendation_id
    payload = {"sections": sections.model_dump(mode="json"), "sources": sources}
    version = await append_version(session, report, payload=payload, source=source, status=status, edited_by=actor.id)
    if commit:
        await session.commit()
    return await _present(session, actor, case, report, version)


def _carry(
    fresh: Sections,
    sources: dict[str, str],
    previous: Sections,
    previous_sources: dict[str, str],
) -> tuple[Sections, dict[str, str]]:
    """Keep HR-only fields the composer does not read from the case row."""
    employee = fresh.employee_information.model_dump()
    kept = False
    for key in ("department", "position", "employment_status"):
        if not employee.get(key) and getattr(previous.employee_information, key):
            employee[key] = getattr(previous.employee_information, key)
            kept = True
    incident = fresh.incident_summary.model_dump()
    if not incident["timeline"] and previous.incident_summary.timeline:
        incident["timeline"] = previous.incident_summary.timeline
    if not incident["employee_statement"] and previous.incident_summary.employee_statement:
        incident["employee_statement"] = previous.incident_summary.employee_statement
    data = fresh.model_dump()
    data["employee_information"] = employee
    data["incident_summary"] = incident
    if kept and previous_sources.get("employee_information.employee_name") == "HR":
        sources["employee_information.employee_name"] = "HR"
    return Sections.model_validate(data), sources


def _merge(sections: Sections, sources: dict[str, str], patch: AssessmentPatch) -> tuple[Sections, dict[str, str]]:
    data = sections.model_dump()
    if patch.case_information is not None:
        incoming = patch.case_information
        data["case_information"]["incident_date"] = incoming.incident_date
        data["case_information"]["violation_type"] = incoming.violation_type
        data["case_information"]["description"] = incoming.description
        sources["case_information.description"] = "HR"
    if patch.employee_information is not None:
        data["employee_information"] = patch.employee_information.model_dump()
        sources["employee_information.employee_name"] = "HR"
    if patch.incident_summary is not None:
        data["incident_summary"] = patch.incident_summary.model_dump()
        sources["incident_summary.narrative"] = "HR"
    if patch.confirmed_facts is not None:
        merged: list[ConfirmedFact] = []
        for item in sections.confirmed_facts:
            edited = next((row for row in patch.confirmed_facts if row.fact_key == item.fact_key), None)
            if edited is None:
                merged.append(item)
                continue
            value = edited.value
            changed = value != item.value
            status = item.status
            source = item.source
            blocking = item.blocking
            if changed:
                source = "HR"
                if value:
                    status = "HR_EDITED"
                    blocking = False
                elif item.blocking or item.status == "MISSING":
                    status = "MISSING"
                    blocking = True
                else:
                    status = "UNCERTAIN"
                    blocking = False
            merged.append(
                item.model_copy(update={"value": value, "status": status, "source": source, "blocking": blocking})
            )
            sources[f"confirmed_facts.{item.fact_key}"] = source
        data["confirmed_facts"] = [item.model_dump() for item in merged]
    if patch.handling_rationale is not None:
        data["handling_proposal"]["rationale"] = patch.handling_rationale
        data["handling_proposal"]["manual_text"] = patch.handling_rationale
        sources["handling_proposal.rationale"] = "HR"
    return Sections.model_validate(data), sources


async def _apply_case_edits(session: AsyncSession, actor: User, case: Case, patch: AssessmentPatch) -> None:
    if patch.case_information is not None:
        case.description = patch.case_information.description
        case.incident_date = patch.case_information.incident_date
        if patch.case_information.violation_type in {"UNAUTHORIZED_ABSENCE", "LATE", "GENERAL"}:
            case.family = patch.case_information.violation_type
    if patch.employee_information is not None:
        case.employee_name = patch.employee_information.employee_name
        case.employee_code = patch.employee_information.employee_code
    if patch.confirmed_facts is None:
        return
    rows = {row.fact_key: row for row in await list_fact_rows(session, case.id)}
    for item in patch.confirmed_facts:
        row = rows.get(item.fact_key)
        if row is None or item.value == row.fact_value:
            continue
        row.fact_value = item.value
        if item.value:
            row.confirmed = True
            row.confirmed_by = actor.id
            row.confirmed_at = utc_now()
        else:
            row.confirmed = False
            row.confirmed_by = None
            row.confirmed_at = None


def _stored_chunk_ids(answer: AnswerView | None) -> set[str]:
    """Chunk ids on the stored recommendation. The form may not cite anything else."""
    if answer is None:
        return set()
    found: set[str] = set()
    layers = (answer.legal_basis, answer.internal_rule, answer.precedent, answer.inspection_risk)
    for layer in layers:
        for item in layer:
            if item.chunk_id is not None:
                found.add(str(item.chunk_id))
    return found


async def _checked(session: AsyncSession, case: Case, sections: Sections):
    answer = await load(session, case)
    return validate_sections(sections, _stored_chunk_ids(answer))


async def _present(
    session: AsyncSession,
    actor: User,
    case: Case,
    report: AssessmentReport,
    version: AssessmentVersion,
) -> AssessmentView:
    sections, sources = _saved(version)
    answer = await load(session, case)
    validation = validate_sections(sections, _stored_chunk_ids(answer) if answer is not None else set())
    if any(card.chunk_id is None for card in sections.citations):
        validation.warnings.append("Một số căn cứ chỉ còn bản trích đã lưu. Pháp chế cần đối chiếu lại liên kết nguồn.")
    ticket = None if answer is None or answer.ticket is None else answer.ticket.disposition
    mutable = case.status in MUTABLE_STATUSES and actor.role in {"HR", "MANAGER"}
    confirmed = version.status == "CONFIRMED"
    view = AssessmentView(
        assessment_id=report.id,
        case_id=case.id,
        version=version.version,
        status="CONFIRMED" if confirmed else "DRAFT",
        form_status=_form_status(version, validation.is_valid),
        sections=sections,
        validation=validation,
        permissions=Permissions(
            can_edit=mutable and not confirmed,
            can_confirm=mutable and not confirmed and validation.is_valid,
            can_reanalyze=mutable and answer is not None,
            can_create_ticket=ticket_allowed(
                confirmed,
                case.status,
                ticket,
                None if answer is None else answer.sanction_type,
            ),
        ),
        metadata=AssessmentMetadata(
            generated_at=version.created_at,
            case_created_date=vietnam_date(case.created_at),
            minutes_profile=minutes_profile(case.case_code, case.created_at),
            source="HR" if version.source == "HR" else "AI",
            recommendation_id=report.recommendation_id,
            prompt_version=_PROMPT,
        ),
        sources=sources,
    )
    return view


def ticket_allowed(
    confirmed: bool,
    case_status: str,
    disposition: str | None,
    sanction_type: str | None,
) -> bool:
    """HR may send after confirming the minutes, including a held report.

    A termination value stays blocked. Chat does not send by itself.
    """
    if not confirmed or case_status != "ANALYZED" or sanction_type == "TERMINATION":
        return False
    return disposition in {"PREVIEW", "HOLD"}


def _can_refresh(actor: User, case: Case, version: AssessmentVersion) -> bool:
    return (
        version.status == "DRAFT"
        and version.source != "HR"
        and case.status in MUTABLE_STATUSES
        and actor.role in {"HR", "MANAGER"}
    )


def _catalog_mismatch(case: Case, sections: Sections) -> bool:
    """True when the draft still requires a fact from another kind of case."""
    wanted = {spec.key for spec in required_specs(resolved_family(case.description or "", case.family))}
    present = {item.fact_key for item in sections.confirmed_facts}
    blocking_outside = {
        item.fact_key for item in sections.confirmed_facts if item.blocking and item.fact_key not in wanted
    }
    return bool(blocking_outside) or not wanted <= present


def _form_status(version: AssessmentVersion, valid: bool) -> FormStatus:
    if version.status == "CONFIRMED":
        return "CONFIRMED"
    if version.status == "SUPERSEDED":
        return "SUPERSEDED"
    if valid:
        return "READY_FOR_CONFIRM"
    if version.source == "HR":
        return "HR_EDITING"
    return "AI_DRAFT"


def _saved(version: AssessmentVersion) -> tuple[Sections, dict[str, str]]:
    payload = version.payload or {}
    sections = Sections.model_validate(payload.get("sections") or {})
    sources = dict(payload.get("sources") or {})
    return sections, sources


async def _open(session: AsyncSession, case_id: UUID) -> tuple[AssessmentReport, AssessmentVersion]:
    report = await get_report(session, case_id)
    if report is None:
        raise AppError(404, "Hồ sơ chưa có biên bản đánh giá.", code="NOT_FOUND")
    version = await current_version(session, report)
    if version is None:
        raise AppError(404, "Hồ sơ chưa có biên bản đánh giá.", code="NOT_FOUND")
    return report, version


async def _case(session: AsyncSession, actor: User, case_id: UUID, level: CaseAccessLevel) -> Case:
    case = await session.get(Case, case_id)
    if case is None:
        raise AppError(404, "Không tìm thấy hồ sơ.", code="CASE_NOT_FOUND")
    await require_case_access(session, actor, case, level)
    return case


async def _editable(session: AsyncSession, actor: User, case_id: UUID) -> Case:
    case = await _case(session, actor, case_id, CaseAccessLevel.EDIT)
    if case.status not in MUTABLE_STATUSES:
        raise AppError(409, "Hồ sơ không còn ở bước sửa biên bản.", code="CASE_NOT_EDITABLE")
    if actor.role not in {"HR", "MANAGER"}:
        raise AppError(403, "Chỉ HR được sửa và xác nhận biên bản.", code="FORBIDDEN")
    return case
