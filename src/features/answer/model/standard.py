"""One company sanction and one process, after the retrieved sources are split.

A level is kept only when the synthesis assessment cites an internal rule and
a law or guiding decree verbatim. An administrative penalty and a precedent
cannot set or raise that level. Termination is never the company sanction.
"""

from src.features.answer.schema import SANCTION_LABELS, AppliedStandard, LayerEffect, ProcessStep

RULE = (
    "Một chuẩn. Mức chỉ được chốt khi đoạn luật hoặc nghị định hướng dẫn và đoạn nội quy "
    "đã retrieval được trích nguyên văn. "
    "Thiếu fact thì chưa chốt. Nhiều mức cùng được chứng minh thì chưa chọn. "
    "Nghị định xử phạt và tiền lệ không đổi mức. "
    "Sa thải và chấm dứt hợp đồng không trộn."
)
_COMPANY = frozenset(set(SANCTION_LABELS) - {"TERMINATION"})


def applied_standard(
    sanction_type: str | None,
    risk_level: str | None,
    steps: list[ProcessStep],
) -> AppliedStandard:
    """Wrap the chosen level so each layer keeps a single effect."""
    adopted = sanction_type if sanction_type in _COMPANY else None
    aligned = adopted is not None
    return AppliedStandard(
        sanction_type=adopted,
        process_steps=list(steps),
        risk_level=risk_level,
        aligned=aligned,
        rule=RULE,
        layers=[
            LayerEffect(
                layer="legal_basis",
                effect="basis",
                note="Luật và nghị định hướng dẫn chỉ đứng khi được trích nguyên văn.",
            ),
            LayerEffect(
                layer="internal_rule",
                effect="level" if aligned else "open",
                note=(
                    "Mức lấy từ đoạn nội quy được trích nguyên văn."
                    if aligned
                    else "Chưa có mức nội quy nào được trích dẫn đủ."
                ),
            ),
            LayerEffect(layer="precedent", effect="compare", note="Tiền lệ không nâng mức."),
            LayerEffect(
                layer="inspection_risk",
                effect="excluded",
                note="Nghị định xử phạt không vào mức kỷ luật.",
            ),
        ],
    )
