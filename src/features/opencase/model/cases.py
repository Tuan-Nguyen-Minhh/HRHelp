"""Open a case and read it back for the person who created it."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.case_graph import build_case_graph
from src.common.access import require_case, require_case_role
from src.common.errors import AppError
from src.features.cite.model.search import search_policies
from src.features.opencase.model.store import (
    NewCase,
    find_by_code,
    get_active_conversation,
    insert_case,
    insert_conversation,
)
from src.features.opencase.schema import CaseView, OpenCaseRequest, OpenCaseResponse
from src.models.cases import Case
from src.models.conversations import Conversation
from src.models.users import User


async def open_case(session: AsyncSession, actor: User, payload: OpenCaseRequest) -> OpenCaseResponse:
    """Create the case and its first conversation.

    A duplicate ``case_code`` is rejected before insert and again if two
    requests pass the check together.
    """
    require_case_role(actor)

    async def opener(state: dict) -> dict:
        if await find_by_code(session, state["case_code"]) is not None:
            raise AppError(409, "Mã hồ sơ đã tồn tại.")
        case = await insert_case(session, state["actor_id"], _new_case(payload))
        conversation = await insert_conversation(session, state["actor_id"], case)
        return {"case_id": case.id, "conversation_id": conversation.id, "status": case.status}

    graph = build_case_graph(lambda query: search_policies(session, query), opener)
    try:
        state = await graph.ainvoke(
            {
                "step": "open",
                "actor_id": actor.id,
                "case_code": payload.case_code,
                "employee_code": payload.employee_code,
                "employee_name": payload.employee_name,
                "description": payload.description,
                "incident_date": payload.incident_date,
            }
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if "case_code" not in str(getattr(exc, "orig", exc)).lower():
            raise
        raise AppError(409, "Mã hồ sơ đã tồn tại.") from None
    return OpenCaseResponse(
        case_id=state["case_id"], conversation_id=state["conversation_id"], status=state["status"]
    )


async def get_case(session: AsyncSession, actor: User, case_id: UUID) -> CaseView:
    """Return the case header for its creator."""
    case = await require_case(session, case_id, actor)
    conversation = await get_active_conversation(session, case.id)
    return _view(case, conversation.id if conversation else None)


async def active_conversation(session: AsyncSession, case_id: UUID) -> Conversation | None:
    """Return the open conversation other features append messages to."""
    return await get_active_conversation(session, case_id)


def _new_case(payload: OpenCaseRequest) -> NewCase:
    return NewCase(
        case_code=payload.case_code,
        employee_code=payload.employee_code,
        employee_name=payload.employee_name,
        description=payload.description,
        incident_date=payload.incident_date,
    )


def _view(case: Case, conversation_id: UUID | None) -> CaseView:
    return CaseView(
        case_id=case.id,
        conversation_id=conversation_id,
        case_code=case.case_code,
        employee_code=case.employee_code,
        employee_name=case.employee_name,
        description=case.description,
        incident_date=case.incident_date,
        status=case.status,
    )
