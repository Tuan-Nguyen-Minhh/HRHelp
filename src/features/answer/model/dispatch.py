"""Feature 7 graph: hold a proposal or draft the legal ticket.

The node functions read ``state['proposal']`` only. They do not open a session,
search policies, or choose a new sanction.
"""

import json
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.features.answer.model.proposal import ProposalHandoff
from src.features.answer.schema import SANCTION_LABELS, CitationView, ProcessStep

DRAFT_TYPES = ("MINUTES", "EXPLANATION_REQUEST", "DECISION", "TICKET")
_LEVELS = frozenset({"WARNING", "REPRIMAND", "WAGE_POSTPONEMENT", "DEMOTION", "DISMISSAL"})
_HOLD_TEXT = {
    "TERMINATION": "Message mang mức chấm dứt hợp đồng. Hồ sơ được giữ lại, chưa chuyển pháp chế.",
    "OPEN_SANCTION": "Mức chưa được khóa để ban hành. Hồ sơ được giữ lại, chưa chuyển pháp chế.",
    "RISK_HIGH": "Mức rủi ro còn cao. Hồ sơ được giữ lại, chưa chuyển pháp chế.",
    "MISSING_INTERNAL_RULE": "Chưa có nội quy còn hiệu lực. Hồ sơ được giữ lại, chưa chuyển pháp chế.",
    "PROCEDURE_OPEN": "Biên bản hoặc yêu cầu giải trình chưa xong. Hồ sơ được giữ lại, chưa chuyển pháp chế.",
}


@dataclass(frozen=True)
class DraftText:
    """One case draft the caller may store. The graph does not write the row."""

    draft_type: str
    title: str
    content: str


@dataclass(frozen=True)
class DispatchResult:
    """``HOLD`` keeps the recommendation draft. ``SUBMIT`` carries four draft texts."""

    disposition: str
    hold_code: str | None
    reason: str
    drafts: tuple[DraftText, ...] = ()


class DispatchState(TypedDict, total=False):
    """Input is only ``proposal``. ``result`` is what the caller persists."""

    proposal: ProposalHandoff
    result: DispatchResult


def build_dispatch_agent() -> CompiledStateGraph:
    """Compile gate → draft. A hold ends at the gate."""
    graph = StateGraph(DispatchState)
    graph.add_node("gate", gate_node)
    graph.add_node("draft", draft_node)
    graph.set_entry_point("gate")
    graph.add_conditional_edges("gate", _after_gate, {"draft": "draft", "end": END})
    graph.add_edge("draft", END)
    return graph.compile()


def gate_node(state: dict) -> dict:
    """Decide hold or submit from the proposal fields.

    A hold still carries the review minutes so HR can read the assessment.
    The legal ticket is filled only when the gate submits.
    """
    proposal = _proposal(state)
    code = hold_code(proposal)
    if code is None:
        return {"result": DispatchResult("SUBMIT", None, "")}
    return {
        "result": DispatchResult(
            "HOLD",
            code,
            _hold_reason(proposal, code),
            (_review_minutes(proposal),),
        )
    }


def draft_node(state: dict) -> dict:
    """Fill four drafts from the proposal. The sanction is copied, not recomputed."""
    proposal = _proposal(state)
    label = _level(proposal)
    return {
        "result": DispatchResult(
            "SUBMIT",
            None,
            f"Đủ căn cứ để chuyển pháp chế. Mức đề xuất là {label}.",
            _drafts(proposal, label),
        )
    }


def drafts_for_review(proposal: ProposalHandoff) -> DispatchResult:
    """Four drafts after HR confirmed the minutes. The stored level is copied.

    Chat still holds when the gate fails. This runs only because HR chose to send.
    """
    label = _level(proposal)
    return DispatchResult(
        "SUBMIT",
        None,
        f"HR đã xác nhận biên bản và gửi phiếu. Mức trong báo cáo là {label}.",
        _drafts(proposal, label),
    )


def ready_to_dispatch(case_status: str, recommendation_status: str | None) -> bool:
    """Dispatch once, only while that proposal is still a draft on an analyzed case."""
    return case_status == "ANALYZED" and recommendation_status == "DRAFT"


def hold_code(proposal: ProposalHandoff) -> str | None:
    """First failing condition, or None when the ticket may be sent."""
    return hold_fields(
        proposal.sanction_type,
        proposal.risk_level,
        proposal.missing_internal_rule,
        proposal.process_steps,
    )


def hold_fields(
    sanction_type: str | None,
    risk_level: str | None,
    missing_internal_rule: bool,
    process_steps: list[ProcessStep],
) -> str | None:
    """Same gate as ``hold_code``, read from stored answer fields."""
    if sanction_type == "TERMINATION":
        return "TERMINATION"
    if sanction_type not in _LEVELS:
        return "OPEN_SANCTION"
    if risk_level in {"HIGH", "CRITICAL"}:
        return "RISK_HIGH"
    if missing_internal_rule:
        return "MISSING_INTERNAL_RULE"
    done = {step.code: step.done for step in process_steps}
    if not done.get("MINUTES") or not done.get("EXPLANATION_REQUEST"):
        return "PROCEDURE_OPEN"
    return None


def hold_reason(code: str) -> str:
    """Short Vietnamese reason for one hold code."""
    return _HOLD_TEXT[code]


def _after_gate(state: dict) -> str:
    result = state.get("result")
    if isinstance(result, DispatchResult) and result.disposition == "SUBMIT":
        return "draft"
    return "end"


def _proposal(state: dict) -> ProposalHandoff:
    proposal = state.get("proposal")
    if not isinstance(proposal, ProposalHandoff):
        raise TypeError("Dispatch agent expects state['proposal'] to be a ProposalHandoff.")
    return proposal


def _hold_reason(proposal: ProposalHandoff, code: str) -> str:
    text = proposal.rationale.strip()
    if text:
        return text
    return _HOLD_TEXT[code]


def _drafts(proposal: ProposalHandoff, label: str) -> tuple[DraftText, ...]:
    identity = _identity(proposal)
    steps = _steps(proposal)
    return (
        _review_minutes(proposal),
        DraftText("EXPLANATION_REQUEST", "Yêu cầu giải trình", _explanation(identity)),
        DraftText("DECISION", "Dự thảo quyết định kỷ luật", _decision(proposal, identity, steps, label)),
        DraftText("TICKET", _ticket_title(proposal), _ticket(proposal)),
    )


def _review_minutes(proposal: ProposalHandoff) -> DraftText:
    """One biên bản HR reads before confirming. The level is copied, not chosen here."""
    return DraftText("MINUTES", "Biên bản đánh giá", _minutes_body(proposal))


def _minutes_body(proposal: ProposalHandoff) -> str:
    report = proposal.message.strip()
    if report.startswith("BIÊN BẢN ĐÁNH GIÁ VỤ VIỆC"):
        return report
    finding = proposal.rationale.strip() or "Chưa có nhận định từ các đoạn đã lấy."
    penalty = _quotes(proposal.inspection_risk) if proposal.inspection_risk else "Không có đoạn xử phạt hành chính."
    return "\n\n".join(
        [
            _identity(proposal),
            (
                "Biên bản tập hợp tình tiết đã khóa, đoạn văn bản đã truy xuất và kết quả đánh giá. "
                "HR xem biên bản này rồi chốt. Biên bản không tự ban hành quyết định."
            ),
            f"Kết quả đánh giá\n{finding}",
            f"Mức trong báo cáo\n{_level(proposal)}",
            f"Rủi ro căn cứ\n{proposal.risk_level or 'Chưa có'}",
            f"Quy trình\n{_steps(proposal)}",
            f"Luật và nghị định hướng dẫn\n{_quotes(proposal.legal_basis)}",
            f"Nội quy\n{_quotes(proposal.internal_rule)}",
            f"Tiền lệ\n{_quotes(proposal.precedent) if proposal.precedent else 'Không có đoạn tiền lệ.'}",
            f"Xử phạt hành chính\nNhóm này không phải mức kỷ luật của người lao động.\n{penalty}",
        ]
    )


def _explanation(identity: str) -> str:
    return (
        f"{identity}\n\n"
        "Đã gửi yêu cầu giải trình. Không thêm hạn trả lời khi fact không nêu hạn."
    )


def _decision(proposal: ProposalHandoff, identity: str, steps: str, label: str) -> str:
    return "\n\n".join(
        [
            identity,
            f"Mức chế tài\n{label}",
            f"Nhận định\n{proposal.rationale or 'Không có nhận định.'}",
            f"Quy trình\n{steps}",
            f"Căn cứ công ty được áp\n{_quotes(proposal.legal_basis)}",
            f"Mức nội quy đúng ngày\n{_quotes(proposal.internal_rule)}",
            f"Tiền lệ\n{_quotes(proposal.precedent) if proposal.precedent else 'Không có đoạn tiền lệ. Tiền lệ không tự nâng mức.'}",
            (
                "Cảnh báo thanh tra\n"
                + (
                    _quotes(proposal.inspection_risk)
                    if proposal.inspection_risk
                    else "Không có đoạn cảnh báo thanh tra."
                )
            ),
            "Bản thảo. Chưa có mã quyết định. Chưa có người ký.",
        ]
    )


def _ticket(proposal: ProposalHandoff) -> str:
    payload = {
        "employee": {"name": proposal.employee_name, "code": proposal.employee_code},
        "case": {
            "case_id": str(proposal.case_id),
            "incident_date": proposal.incident_date.isoformat(),
            "family": proposal.family,
        },
        "facts": dict(proposal.facts),
        "legal": {"code": proposal.legal_code},
        "violation": {
            "summary": proposal.rationale.strip() or proposal.message.strip(),
            "sanction_type": proposal.sanction_type,
        },
        "risk": proposal.risk_level,
        "process_steps": [
            {"code": step.code, "label": step.label, "done": step.done} for step in proposal.process_steps
        ],
        "citations": [_citation_payload(item) for item in _ticket_citations(proposal)],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _ticket_citations(proposal: ProposalHandoff) -> list[CitationView]:
    return [
        *proposal.legal_basis,
        *proposal.internal_rule,
        *proposal.precedent,
        *proposal.inspection_risk,
    ]


def _citation_payload(item: CitationView) -> dict[str, str | None]:
    return {
        "policy_type": item.policy_type,
        "policy_code": item.policy_code,
        "policy_name": item.policy_name,
        "quote": item.quote,
        "article": item.article,
        "clause": item.clause,
        "point": item.point,
        "chunk_id": str(item.chunk_id) if item.chunk_id else None,
    }


def _identity(proposal: ProposalHandoff) -> str:
    who = proposal.employee_name or "nhân viên"
    when = proposal.incident_date.strftime("%d/%m/%Y")
    lines = [f"Nhân viên: {who}", f"Ngày xảy ra: {when}", f"Nhóm vụ: {proposal.family}"]
    lines.extend(proposal.fact_lines)
    return "\n".join(lines)


def _steps(proposal: ProposalHandoff) -> str:
    rows = []
    for index, step in enumerate(proposal.process_steps, start=1):
        mark = "đã có" if step.done else "chưa có"
        rows.append(f"{index}. {step.label} ({mark})")
    return "\n".join(rows) or "Không có bước thủ tục."


def _quotes(items: list[CitationView]) -> str:
    if not items:
        return "Không có đoạn."
    return "\n".join(_quote(item) for item in items)


def _quote(item: CitationView) -> str:
    place = []
    if item.article:
        place.append(f"Điều {item.article}")
    if item.clause:
        place.append(f"khoản {item.clause}")
    if item.point:
        place.append(f"điểm {item.point}")
    where = " ".join(place)
    code = item.policy_code or item.policy_name or "văn bản"
    head = f"{code} {where}".strip()
    chunk = f" [{item.chunk_id}]" if item.chunk_id else ""
    return f"- {head}{chunk}: {item.quote}"


def _level(proposal: ProposalHandoff) -> str:
    if proposal.sanction_type in SANCTION_LABELS:
        return SANCTION_LABELS[proposal.sanction_type]
    if proposal.sanction_type:
        return proposal.sanction_type
    return "Báo cáo chưa ghi một mức. Kết quả nằm ở phần nhận định của biên bản."


def _ticket_title(proposal: ProposalHandoff) -> str:
    if not proposal.employee_name:
        return "Phiếu chuyển pháp chế"
    return _clip_title(f"Phiếu chuyển pháp chế — {proposal.employee_name}")


def _clip_title(text: str) -> str:
    if len(text) <= 255:
        return text
    return text[:254] + "…"
