"""One company sanction and one process, after the retrieved sources are split.

The matching internal rule states the company level. Law and a guiding decree
state the ceiling. A level is kept only when both say so. An administrative
penalty and a precedent cannot set or raise that level. Termination is never
the company sanction.
"""

from src.features.answer.schema import SANCTION_LABELS, AppliedStandard, LayerEffect, ProcessStep

RULE = (
    "Một chuẩn. Luật và nghị định hướng dẫn là trần mức được dùng. "
    "Nội quy khớp hành vi nêu mức công ty, và chỉ mức còn trong trần được chốt. "
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
                note="Luật và nghị định hướng dẫn là trần mức được dùng.",
            ),
            LayerEffect(
                layer="internal_rule",
                effect="level" if aligned else "open",
                note=(
                    "Mức lấy từ đoạn nội quy khớp hành vi và còn trong trần."
                    if aligned
                    else "Chưa có mức nội quy nào khớp hành vi và còn trong trần."
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
