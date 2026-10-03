"""MCP-style tools for case documents.

The app does not ship an MCP server yet, so this module keeps the tool schemas
and dispatcher close to the domain code. A future MCP transport can expose
``CASE_TOOL_SCHEMAS`` and call ``call_case_tool`` without duplicating business
rules.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.common.clock import utc_now
from src.features.answer.schema import AnswerView, CitationView, SANCTION_LABELS
from src.models.cases import Case

CaseToolName = Literal[
    "create_violation_minutes_form",
    "create_legal_ticket_form",
    "export_case_document_word",
]

_EXPORT_DIR = Path("/tmp/hr_case_exports")


class CaseToolCall(BaseModel):
    """One tool request, shaped like an MCP tool invocation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: CaseToolName
    arguments: dict[str, Any] = Field(default_factory=dict)


class CaseToolResult(BaseModel):
    """Structured result returned by the case document tools."""

    name: str
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class CaseDocument:
    """A renderable case document."""

    title: str
    sections: tuple[tuple[str, str], ...]

    @property
    def content(self) -> str:
        return "\n\n".join([self.title, *[f"{heading}\n{body}" for heading, body in self.sections]])


CASE_TOOL_SCHEMAS: tuple[dict[str, Any], ...] = (
    {
        "name": "create_violation_minutes_form",
        "description": "Create a Vietnamese internal-rule violation minutes form from a case and recommendation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_citations": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "create_legal_ticket_form",
        "description": "Create a legal review ticket form from a stored recommendation and drafts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "legal_code": {"type": "string", "description": "Legal officer email or code, when selected."},
            },
        },
    },
    {
        "name": "export_case_document_word",
        "description": "Export a case document to a .docx file.",
        "input_schema": {
            "type": "object",
            "required": ["document_type"],
            "properties": {
                "document_type": {
                    "type": "string",
                    "enum": ["minutes", "ticket", "assessment"],
                },
                "file_name": {"type": "string"},
            },
        },
    },
)


async def call_case_tool(case: Case, answer: AnswerView | None, call: CaseToolCall) -> CaseToolResult:
    """Dispatch one safe case-document tool call."""
    if call.name == "create_violation_minutes_form":
        document = violation_minutes_document(
            case,
            answer,
            include_citations=bool(call.arguments.get("include_citations", True)),
        )
        return CaseToolResult(name=call.name, title=document.title, content=document.content)
    if call.name == "create_legal_ticket_form":
        document = legal_ticket_document(case, answer, legal_code=call.arguments.get("legal_code"))
        return CaseToolResult(name=call.name, title=document.title, content=document.content)
    if call.name == "export_case_document_word":
        document_type = str(call.arguments.get("document_type") or "")
        document = _document_for_type(case, answer, document_type)
        path = export_word_document(document, call.arguments.get("file_name"))
        return CaseToolResult(
            name=call.name,
            title=document.title,
            content=document.content,
            metadata={"format": "docx", "path": str(path), "file_name": path.name},
        )
    raise ValueError(f"Unsupported case tool: {call.name}")


def violation_minutes_document(
    case: Case,
    answer: AnswerView | None,
    *,
    include_citations: bool = True,
) -> CaseDocument:
    """Create a company-rule violation minutes form.

    The structure follows common Vietnamese HR minutes forms: company header,
    time/place, reporter, employee, violation content, damage, employee opinion,
    proposed handling, and signatures. It is not a copy of any third-party form.
    """
    facts = _facts(answer)
    sections = [
        ("Thời gian, địa điểm", _event_line(case)),
        ("Người lập biên bản", "Họ tên: ........................................\nChức vụ/Bộ phận: ................................"),
        ("Người bị lập biên bản", _employee(case)),
        ("Nội dung vi phạm", _violation_content(case, facts)),
        ("Thiệt hại vật chất", facts.get("damage", "Chưa ghi nhận hoặc chưa xác định.")),
        ("Ý kiến của người bị lập biên bản", "................................................................................"),
        ("Hình thức xử lý/đề xuất", _sanction(answer)),
        ("Xác nhận quy trình", _process(answer)),
    ]
    if include_citations and answer is not None:
        sections.append(("Căn cứ tham khảo", _citations(answer)))
    sections.append(("Chữ ký", "Người lập biên bản: ....................\nNgười bị lập biên bản: ...................."))
    return CaseDocument("BIÊN BẢN GHI NHẬN VI PHẠM NỘI QUY", tuple(sections))


def legal_ticket_document(case: Case, answer: AnswerView | None, *, legal_code: str | None = None) -> CaseDocument:
    """Create the legal review ticket form. This does not submit the ticket."""
    if answer is None:
        sections = [
            ("Trạng thái", "Hồ sơ chưa có báo cáo đánh giá để lập phiếu pháp chế."),
            ("Hồ sơ", _case_line(case)),
        ]
        return CaseDocument("PHIẾU CHUYỂN PHÁP CHẾ", tuple(sections))
    sections = [
        ("Hồ sơ", _case_line(case)),
        ("Người lao động", _employee(case)),
        ("Người nhận pháp chế", legal_code or "Chưa chọn."),
        ("Tóm tắt đề xuất", answer.rationale or answer.message),
        ("Mức đề xuất", _sanction(answer)),
        ("Rủi ro", answer.risk_level or "Chưa xác định."),
        ("Quy trình", _process(answer)),
        ("Căn cứ", _citations(answer)),
    ]
    return CaseDocument("PHIẾU CHUYỂN PHÁP CHẾ", tuple(sections))


def assessment_document(case: Case, answer: AnswerView | None) -> CaseDocument:
    if answer is None:
        return CaseDocument("BÁO CÁO ĐÁNH GIÁ", (("Trạng thái", "Hồ sơ chưa có báo cáo đánh giá."),))
    return CaseDocument(
        "BÁO CÁO ĐÁNH GIÁ VỤ VIỆC",
        (
            ("Hồ sơ", _case_line(case)),
            ("Người lao động", _employee(case)),
            ("Nội dung báo cáo", answer.message),
            ("Mức đề xuất", _sanction(answer)),
            ("Căn cứ", _citations(answer)),
        ),
    )


def export_word_document(document: CaseDocument, file_name: str | None = None) -> Path:
    """Write one document to .docx and return the local file path."""
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError as exc:  # pragma: no cover - depends on deployment package set.
        raise RuntimeError("python-docx is required to export Word files.") from exc

    _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = _EXPORT_DIR / _safe_file_name(file_name or document.title)
    doc = Document()
    header = doc.add_paragraph("CÔNG TY: ........................................")
    header.alignment = WD_ALIGN_PARAGRAPH.LEFT
    motto = doc.add_paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc")
    motto.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title = doc.add_heading(document.title, level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for heading, body in document.sections:
        doc.add_heading(heading, level=2)
        for line in body.splitlines() or [""]:
            doc.add_paragraph(line)
    doc.add_paragraph(f"Ngày xuất: {utc_now().date().isoformat()}")
    doc.save(path)
    return path


def _document_for_type(case: Case, answer: AnswerView | None, document_type: str) -> CaseDocument:
    if document_type == "minutes":
        return violation_minutes_document(case, answer)
    if document_type == "ticket":
        return legal_ticket_document(case, answer)
    if document_type == "assessment":
        return assessment_document(case, answer)
    raise ValueError("document_type must be one of: minutes, ticket, assessment.")


def _event_line(case: Case) -> str:
    date = case.incident_date.isoformat() if case.incident_date else "....../....../......"
    return f"Vào ngày {date}, tại ........................................"


def _case_line(case: Case) -> str:
    return f"Mã hồ sơ: {case.case_code}\nNgày vụ việc: {case.incident_date or 'Chưa ghi'}"


def _employee(case: Case) -> str:
    return "\n".join(
        [
            f"Họ tên: {case.employee_name or '........................................'}",
            f"Mã nhân viên: {case.employee_code or '........................................'}",
            "Chức vụ/Bộ phận: ........................................",
        ]
    )


def _facts(answer: AnswerView | None) -> dict[str, str]:
    if answer is None:
        return {}
    standard = answer.standard
    data = {"risk_level": answer.risk_level or ""}
    if standard is not None:
        data["process"] = _process(answer)
    return data


def _violation_content(case: Case, facts: dict[str, str]) -> str:
    lines = [case.description or "................................................................................"]
    if facts.get("risk_level"):
        lines.append(f"Mức rủi ro đánh giá: {facts['risk_level']}")
    return "\n".join(lines)


def _sanction(answer: AnswerView | None) -> str:
    if answer is None or not answer.sanction_type:
        return "Chưa đủ căn cứ để khóa hình thức xử lý."
    return SANCTION_LABELS.get(answer.sanction_type, answer.sanction_type)


def _process(answer: AnswerView | None) -> str:
    if answer is None or not answer.process_steps:
        return "Chưa có dữ liệu quy trình."
    return "\n".join(f"- {step.label}: {'đã xong' if step.done else 'chưa xong'}" for step in answer.process_steps)


def _citations(answer: AnswerView | None) -> str:
    if answer is None:
        return "Chưa có căn cứ."
    rows = [*answer.legal_basis, *answer.internal_rule, *answer.precedent, *answer.inspection_risk]
    if not rows:
        return "Chưa có căn cứ."
    return "\n".join(_citation(item) for item in rows[:8])


def _citation(item: CitationView) -> str:
    location = " ".join(part for part in (item.article, item.clause, item.point) if part)
    label = item.policy_name or item.policy_code or "Văn bản"
    if location:
        label = f"{label} - {location}"
    quote = " ".join(item.quote.split())
    return f"- {label}: {quote}"


def _safe_file_name(value: str) -> str:
    raw = value.strip()
    if raw.lower().endswith(".docx"):
        raw = raw[:-5]
    folded = "".join(ch if ch.isalnum() else "_" for ch in raw.lower())
    folded = "_".join(part for part in folded.split("_") if part)
    if not folded:
        folded = "case_document"
    folded = f"{folded}_{utc_now().strftime('%Y%m%d%H%M%S')}"
    return f"{folded}.docx"
