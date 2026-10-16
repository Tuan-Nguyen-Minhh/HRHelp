"""Lexical hypotheses for semantic recheck; these rules never select a graph edge."""

import re
from dataclasses import asdict, dataclass

from src.features.clarify.model.system_help import fold_text


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    candidate_route: str
    matched_text: str
    evidence_form: str = "normalized_latest_message"


_RULES = (
    (
        "mentions_authority_action",
        "unsupported",
        r"phe duyet|ky duyet|ky quyet dinh|dong ho so|xoa ho so|bo qua (?:duyet|phap che)|quyet dinh thay",
    ),
    (
        "mentions_public_source",
        "external_research",
        r"web|nguon (?:ben ngoai|ngoai|cong khai)|tra cuu nguon|molisa\.gov\.vn|chinhphu\.vn|vbpl\.vn",
    ),
    ("mentions_recency", "external_research", r"moi nhat|hien nay"),
    ("mentions_policy", "policy_qa", r"theo noi quy|theo quy dinh|can cu|dieu khoan|muc ky luat|luat|nghi dinh"),
    ("mentions_fact", "fact_planner", r"ngay xay ra|phong ban|chuc danh|nghi|di muon|roi vi tri"),
    (
        "mentions_workflow",
        "workflow_action",
        r"tao phieu|lap bien ban|soan bien ban|gui phap che|xem danh gia|tiep tuc quyet dinh",
    ),
    ("mentions_case", "case_qa", r"ho so nay|case nay|nhan vien nay|tinh trang|dang luu"),
    ("mentions_product_help", "system_help", r"ban la ai|chuc nang|tinh nang|ban co the|he thong ho tro|quyen han"),
    ("mentions_social", "general_chat", r"hello|hi|chao ban|cam on|an gi|noi chuyen|tro chuyen|ke chuyen vui"),
)


def detect_route_hypotheses(message: str) -> list[dict]:
    normalized = fold_text(message)
    found = []
    for rule_id, route, pattern in _RULES:
        match = re.search(r"\b(?:" + pattern + r")\b", normalized)
        if match:
            found.append(asdict(RuleMatch(rule_id, route, match.group())))
    return found
