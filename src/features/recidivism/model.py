"""Count issued decisions for the same employee and violation type.

Embedding similarity is not a recurrence signal. The stored fact stays
unconfirmed until HR confirms it, so assessment does not read it before that.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.access import require_mutable_case
from src.common.audit import write_audit
from src.features.clarify.model.store import FactWrite, write_fact
from src.features.recidivism.schema import PriorCase, PriorDecision, RecidivismView
from src.models.case_facts import CaseFact
from src.models.case_violations import CaseViolation
from src.models.cases import Case
from src.models.disciplinary_decisions import DisciplinaryDecision
from src.models.users import User
from src.models.violation_types import ViolationType


async def inspect_recidivism(session: AsyncSession, actor: User, case_id: UUID) -> RecidivismView:
    """Search decided cases and store an unconfirmed count."""
    case = await require_mutable_case(session, case_id, actor)
    type_ids = await _violation_ids(session, case)
    priors = await _priors(session, case, type_ids)
    count = len(priors)
    possible = count > 0 and bool(type_ids)
    confirmed = await _store_unconfirmed(session, actor, case, count, priors)
    await session.commit()
    return RecidivismView(
        case_id=case.id,
        prior_sanction_count=count,
        prior_cases=[PriorCase(case_id=item.id, case_code=item.case_code, status=item.status) for item, _ in priors],
        prior_decisions=[
            PriorDecision(
                decision_code=decision.decision_code,
                sanction_type=decision.sanction_type,
                issued_at=decision.issued_at,
            )
            for _, decision in priors
        ],
        possible_recurrence=possible,
        confirmed=confirmed,
    )


async def _violation_ids(session: AsyncSession, case: Case) -> set[UUID]:
    linked = list(
        (await session.scalars(select(CaseViolation.violation_type_id).where(CaseViolation.case_id == case.id))).all()
    )
    found = set(linked)
    if found or not case.family:
        return found
    catalog = await session.scalar(select(ViolationType.id).where(ViolationType.code == case.family))
    if catalog is not None:
        found.add(catalog)
    return found


async def _priors(
    session: AsyncSession,
    case: Case,
    type_ids: set[UUID],
) -> list[tuple[Case, DisciplinaryDecision]]:
    if not case.employee_code:
        return []
    stmt = (
        select(Case, DisciplinaryDecision)
        .join(DisciplinaryDecision, DisciplinaryDecision.case_id == Case.id)
        .where(
            Case.employee_code == case.employee_code,
            Case.id != case.id,
            Case.status.in_(("DECIDED", "CLOSED")),
        )
    )
    if type_ids:
        stmt = stmt.join(CaseViolation, CaseViolation.case_id == Case.id).where(
            CaseViolation.violation_type_id.in_(type_ids)
        )
    rows = list((await session.execute(stmt)).all())
    unique: dict[UUID, tuple[Case, DisciplinaryDecision]] = {}
    for prior, decision in rows:
        unique[prior.id] = (prior, decision)
    return list(unique.values())


async def _store_unconfirmed(
    session: AsyncSession,
    actor: User,
    case: Case,
    count: int,
    priors: list[tuple[Case, DisciplinaryDecision]],
) -> bool:
    existing = await session.scalar(
        select(CaseFact).where(CaseFact.case_id == case.id, CaseFact.fact_key == "prior_sanction_count")
    )
    if existing is not None and existing.confirmed:
        return True
    codes = ", ".join(decision.decision_code for _, decision in priors) or "không có"
    value = f"{count}; {codes}"
    await write_fact(
        session,
        FactWrite(case.id, "prior_sanction_count", value, False, None, confidence=1.0),
    )
    await write_audit(
        session,
        case_id=case.id,
        actor_id=actor.id,
        actor_role=actor.role,
        action="FACT_CREATED",
        entity_type="case_facts",
        entity_id=case.id,
        after={"fact_key": "prior_sanction_count", "confirmed": False, "prior_sanction_count": count},
    )
    return False
