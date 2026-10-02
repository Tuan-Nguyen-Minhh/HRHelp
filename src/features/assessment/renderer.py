"""Turn a stored form into plain text. The screen renders the JSON, not this string."""

from src.features.assessment.schemas import AssessmentView


def to_markdown(view: AssessmentView) -> str:
    """A readable copy of the form. It is not the document the model returns."""
    case = view.sections.case_information
    employee = view.sections.employee_information
    lines = [
        "BIÊN BẢN ĐÁNH GIÁ VÀ ĐỀ XUẤT XỬ LÝ",
        f"Hồ sơ: {case.case_code}",
        f"Trạng thái biên bản: {view.form_status}",
        "",
        "I. THÔNG TIN VỤ VIỆC",
        case.description,
        "",
        "II. NGƯỜI LAO ĐỘNG",
        employee.employee_name or "",
        employee.employee_code or "",
        "",
        "III. NỘI DUNG",
        view.sections.incident_summary.narrative,
        "",
        "VII. KẾT QUẢ",
        view.sections.assessment_result.status,
        view.sections.assessment_result.summary,
    ]
    return "\n".join(lines)
