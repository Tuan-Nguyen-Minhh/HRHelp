"""Build the API answer from a recommendation row and its citations."""

from uuid import UUID

from src.common.text import clip_quote
from src.features.answer.model.dispatch import hold_fields, hold_reason
from src.features.answer.model.layers import BasisLayer, layer_of
from src.features.answer.model.standard import applied_standard
from src.features.answer.model.store import CitationRow
from src.features.answer.schema import AnswerView, CitationView, DraftView, ProcessStep, TicketRequest
from src.features.cite.model.passage import Passage
from src.models.case_drafts import CaseDraft
from src.models.recommendations import Recommendation

_SUBMITTED = (
    "Đã tạo biên bản, yêu cầu giải trình, dự thảo quyết định và phiếu chuyển pháp chế. Phiếu đang chờ pháp chế xem."
)
_QUEUED = "Hồ sơ đang ở hàng chờ pháp chế."
_AT_MANAGER = "Hồ sơ đang chờ quản lý duyệt lần cuối."
_ISSUED = "Quản lý đã duyệt lần cuối."
_NOT_SENT = "Phiếu chuyển pháp chế chưa được tạo."
_PREVIEW = "Báo cáo đã xong. Xem phiếu bên dưới trước khi đẩy cho pháp chế."


def to_answer_view(recommendation: Recommendation, citations: list[CitationView], case_status: str) -> AnswerView:
    """Group citations into the four layers the screen renders separately."""
    grouped: dict[BasisLayer, list[CitationView]] = {layer: [] for layer in BasisLayer}
    for item in citations:
        grouped[item.layer].append(item)
    steps = _steps(recommendation.process_steps)
    return AnswerView(
        recommendation_id=recommendation.id,
        case_id=recommendation.case_id,
        case_status=case_status,
        agent_run_id=recommendation.agent_run_id,
        rationale=recommendation.rationale,
        sanction_type=recommendation.sanction_type,
        process_steps=steps,
        risk_level=recommendation.risk_level,
        missing_internal_rule=not grouped[BasisLayer.INTERNAL_RULE],
        message=recommendation.recommendation,
        legal_basis=grouped[BasisLayer.LEGAL_BASIS],
        internal_rule=grouped[BasisLayer.INTERNAL_RULE],
        precedent=grouped[BasisLayer.PRECEDENT],
        inspection_risk=grouped[BasisLayer.INSPECTION_RISK],
        standard=applied_standard(recommendation.sanction_type, recommendation.risk_level, steps),
    )


def draft_view(row: CaseDraft) -> DraftView:
    """Copy one stored draft into the answer payload."""
    return DraftView(
        draft_id=row.id,
        draft_type=row.draft_type,
        title=row.title,
        content=row.content,
        status=row.status,
    )


def with_packet(view: AnswerView, drafts: list[DraftView]) -> AnswerView:
    """Attach the current drafts and the ticket request. The sanction stays as stored."""
    return view.model_copy(update={"drafts": list(drafts), "ticket": _ticket(view, drafts)})


def _ticket(view: AnswerView, drafts: list[DraftView]) -> TicketRequest:
    ticket = next((item for item in drafts if item.draft_type == "TICKET" and item.status == "PENDING_REVIEW"), None)
    if view.case_status == "PENDING_LEGAL" and ticket is not None:
        return TicketRequest(disposition="SUBMIT", hold_code=None, reason=_SUBMITTED, queue="PENDING_LEGAL")
    code = hold_fields(view.sanction_type, view.risk_level, view.missing_internal_rule, view.process_steps)
    if code is not None:
        return TicketRequest(disposition="HOLD", hold_code=code, reason=hold_reason(code), queue="HELD")
    preview = next((item for item in drafts if item.draft_type == "TICKET" and item.status == "PREVIEW"), None)
    if view.case_status == "ANALYZED" and preview is not None:
        return TicketRequest(disposition="PREVIEW", hold_code=None, reason=_PREVIEW, queue="READY")
    if view.case_status == "PENDING_LEGAL":
        return TicketRequest(disposition="SUBMIT", hold_code=None, reason=_QUEUED, queue="PENDING_LEGAL")
    if view.case_status == "APPROVED":
        return TicketRequest(disposition="SUBMIT", hold_code=None, reason=_AT_MANAGER, queue="APPROVED")
    if view.case_status in {"DECIDED", "CLOSED"}:
        return TicketRequest(disposition="NOT_SENT", hold_code=None, reason=_ISSUED, queue=view.case_status)
    return TicketRequest(disposition="NOT_SENT", hold_code=None, reason=_NOT_SENT, queue="NOT_SENT")


def view_from_row(row: CitationRow) -> CitationView:
    """Re-layer a stored citation from the policy it was taken from."""
    code = row.policy_code or ""
    name = row.policy_name or ""
    return CitationView(
        citation_id=row.citation_id,
        chunk_id=row.chunk_id,
        layer=layer_of(row.policy_type, code, name),
        policy_type=row.policy_type,
        policy_code=row.policy_code,
        policy_name=row.policy_name,
        quote=row.quote,
        article=row.article,
        clause=row.clause,
        point=row.point,
        score=row.score,
    )


def view_from_passage(citation_id: UUID, passage: Passage) -> CitationView:
    """Layer a passage that was just stored as a citation."""
    return CitationView(
        citation_id=citation_id,
        chunk_id=passage.chunk_id,
        layer=layer_of(passage.policy_type, passage.policy_code, passage.policy_name),
        policy_type=passage.policy_type,
        policy_code=passage.policy_code,
        policy_name=passage.policy_name,
        quote=clip_quote(passage.content),
        article=passage.article,
        clause=passage.clause,
        point=passage.point,
        score=passage.score,
    )


def _steps(raw: object) -> list[ProcessStep]:
    if not isinstance(raw, list):
        return []
    return [ProcessStep.model_validate(item) for item in raw]
