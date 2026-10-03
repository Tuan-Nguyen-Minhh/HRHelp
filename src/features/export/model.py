"""Render persisted case documents as JSON, Markdown, or Word."""

from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.access import require_case
from src.common.errors import AppError
from src.features.answer.model.answers import load_stored
from src.features.answer.model.case_tools import assessment_document, export_word_document, legal_ticket_document
from src.features.assessment.repository import current_version, get_report
from src.features.assessment.schemas import Sections
from src.models.case_drafts import CaseDraft
from src.models.disciplinary_decisions import DisciplinaryDecision
from src.models.users import User

FormatName = Literal["json", "markdown", "docx"]


async def export_assessment(session: AsyncSession, actor: User, case_id: UUID, fmt: FormatName) -> dict:
    case = await require_case(session, case_id, actor)
    view = await load_stored(session, case)
    if fmt == "docx":
        document = assessment_document(case, view, await _assessment_sections(session, case.id))
        return _word("assessment", export_word_document(document), document.content)
    if view is None:
        raise AppError(404, "Hồ sơ chưa có báo cáo.", code="NOT_FOUND")
    payload = {
        "case_id": str(case.id),
        "case_code": case.case_code,
        "recommendation_id": str(view.recommendation_id),
        "sanction_type": view.sanction_type,
        "risk_level": view.risk_level,
        "report": view.message,
    }
    return _render("assessment", payload, view.message, fmt)


async def export_ticket(session: AsyncSession, actor: User, case_id: UUID, fmt: FormatName) -> dict:
    case = await require_case(session, case_id, actor)
    view = await load_stored(session, case)
    if view is None:
        raise AppError(404, "Hồ sơ chưa có phiếu.", code="NOT_FOUND")
    drafts = list(
        (
            await session.scalars(select(CaseDraft).where(CaseDraft.recommendation_id == view.recommendation_id))
        ).all()
    )
    if not drafts:
        raise AppError(404, "Hồ sơ chưa có phiếu đã lưu.", code="NOT_FOUND")
    body = "\n\n".join(f"# {row.title}\n\n{row.content}" for row in drafts)
    payload = {
        "case_id": str(case.id),
        "drafts": [
            {"draft_type": row.draft_type, "title": row.title, "status": row.status, "content": row.content}
            for row in drafts
        ],
    }
    if fmt == "docx":
        document = legal_ticket_document(case, view)
        return _word("ticket", export_word_document(document), document.content)
    return _render("ticket", payload, body, fmt)


async def export_decision(session: AsyncSession, actor: User, case_id: UUID, fmt: FormatName) -> dict:
    case = await require_case(session, case_id, actor)
    decision = await session.scalar(select(DisciplinaryDecision).where(DisciplinaryDecision.case_id == case.id))
    if decision is None:
        raise AppError(404, "Hồ sơ chưa có quyết định.", code="NOT_FOUND")
    payload = {
        "case_id": str(case.id),
        "decision_code": decision.decision_code,
        "sanction_type": decision.sanction_type,
        "summary": decision.summary,
        "legal_basis": decision.legal_basis,
        "is_precedent": bool(decision.is_precedent),
    }
    text = f"# {decision.decision_code}\n\nMức: {decision.sanction_type}\n\n{decision.summary}"
    if decision.legal_basis:
        text += f"\n\n## Căn cứ\n\n{decision.legal_basis}"
    if fmt == "docx":
        from src.features.answer.model.case_tools import CaseDocument

        document = CaseDocument("QUYẾT ĐỊNH KỶ LUẬT", (("Nội dung", text),))
        return _word("decision", export_word_document(document), document.content)
    return _render("decision", payload, text, fmt)


def _render(kind: str, payload: dict, markdown: str, fmt: FormatName) -> dict:
    if fmt == "markdown":
        return {"format": "markdown", "kind": kind, "content": markdown}
    return {"format": "json", "kind": kind, "content": payload}


def _word(kind: str, path, content: str) -> dict:
    return {
        "format": "docx",
        "kind": kind,
        "content": {
            "path": str(path),
            "file_name": path.name,
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "preview": content,
        },
    }


async def _assessment_sections(session: AsyncSession, case_id: UUID) -> Sections | None:
    report = await get_report(session, case_id)
    if report is None:
        return None
    version = await current_version(session, report)
    if version is None:
        return None
    payload = version.payload or {}
    raw = payload.get("sections")
    if not raw:
        return None
    return Sections.model_validate(raw)
