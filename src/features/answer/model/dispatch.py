"""Feature 7 graph: hold a proposal or draft the legal ticket.

The node functions read ``state['proposal']`` only. They do not open a session,
search policies, or choose a new sanction.
"""

from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.features.answer.model.proposal import ProposalHandoff
from src.features.answer.schema import SANCTION_LABELS, CitationView

DRAFT_TYPES = ("MINUTES", "EXPLANATION_REQUEST", "DECISION", "TICKET")
_LEVELS = frozenset({"WARNING", "REPRIMAND", "WAGE_POSTPONEMENT", "DEMOTION", "DISMISSAL"})
_HOLD_TEXT = {
    "TERMINATION": "Message mang mức chấm dứt hợp đồng. Hồ sơ được giữ lại, chưa chuyển pháp chế.",
    "OPEN_SANCTION": "Chưa chốt mức kỷ luật. Hồ sơ được giữ lại, chưa chuyển pháp chế.",
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
    """Decide hold or submit from the proposal fields."""
    proposal = _proposal(state)
    code = hold_code(proposal)
    if code is None:
        return {"result": DispatchResult("SUBMIT", None, "")}
    return {"result": DispatchResult("HOLD", code, _hold_reason(proposal, code))}


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


def hold_code(proposal: ProposalHandoff) -> str | None:
    """First failing condition, or None when the ticket may be sent."""
    if proposal.sanction_type == "TERMINATION":
        return "TERMINATION"
    if proposal.sanction_type not in _LEVELS:
        return "OPEN_SANCTION"
    if proposal.risk_level in {"HIGH", "CRITICAL"}:
        return "RISK_HIGH"
    if proposal.missing_internal_rule:
        return "MISSING_INTERNAL_RULE"
    if not _procedure_done(proposal):
        return "PROCEDURE_OPEN"
    return None


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


def _procedure_done(proposal: ProposalHandoff) -> bool:
    done = {step.code: step.done for step in proposal.process_steps}
    return bool(done.get("MINUTES")) and bool(done.get("EXPLANATION_REQUEST"))


def _drafts(proposal: ProposalHandoff, label: str) -> tuple[DraftText, ...]:
    identity = _identity(proposal)
    steps = _steps(proposal)
    return (
        DraftText("MINUTES", "Biên bản vi phạm", _minutes(identity, steps)),
        DraftText("EXPLANATION_REQUEST", "Yêu cầu giải trình", _explanation(identity)),
        DraftText("DECISION", "Dự thảo quyết định kỷ luật", _decision(proposal, identity, steps, label)),
        DraftText("TICKET", _ticket_title(proposal), _ticket(proposal, identity, steps, label)),
    )


def _minutes(identity: str, steps: str) -> str:
    return (
        f"{identity}\n\n"
        "Biên bản ghi nhận các tình tiết đã khóa. "
        "Không thêm giờ họp hay người lập biên bản ngoài fact.\n\n"
        f"Quy trình\n{steps}"
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


def _ticket(proposal: ProposalHandoff, identity: str, steps: str, label: str) -> str:
    risk = proposal.risk_level or "chưa rõ"
    return "\n\n".join(
        [
            identity,
            f"Mức đề xuất\n{label}",
            f"Mức rủi ro\n{risk}",
            f"Nhận định\n{proposal.rationale or 'Không có nhận định.'}",
            f"Quy trình\n{steps}",
            f"Căn cứ công ty được áp\n{_quotes(proposal.legal_basis)}",
            f"Mức nội quy đúng ngày\n{_quotes(proposal.internal_rule)}",
            f"Tiền lệ\n{_quotes(proposal.precedent) if proposal.precedent else 'Tiền lệ chỉ để đối chiếu, không tự nâng mức.'}",
            (
                "Cảnh báo thanh tra\n"
                + (
                    _quotes(proposal.inspection_risk)
                    if proposal.inspection_risk
                    else "Cảnh báo thanh tra không phải mức kỷ luật."
                )
            ),
        ]
    )


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
    return proposal.sanction_type or "Chưa chốt"


def _ticket_title(proposal: ProposalHandoff) -> str:
    if not proposal.employee_name:
        return "Phiếu chuyển pháp chế"
    return _clip_title(f"Phiếu chuyển pháp chế — {proposal.employee_name}")


def _clip_title(text: str) -> str:
    if len(text) <= 255:
        return text
    return text[:254] + "…"
