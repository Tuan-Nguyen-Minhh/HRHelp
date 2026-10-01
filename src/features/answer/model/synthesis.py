"""Call the evidence-synthesis model, then reject any conclusion the passages do not contain.

The model reads the case facts and the passages feature 5 already retrieved.
It does not search. A quote that is not a verbatim span of its chunk is dropped.
A recommended sanction survives only when an internal-rule quote names that form
and a law or guiding-decree quote is cited with it. Precedent and administrative
penalties cannot carry the sanction. Python does not choose a harsher or lighter level.
"""

import json
import logging
from uuid import UUID

from langchain_openai import ChatOpenAI

from src.agents.handoff import CaseHandoff
from src.core.config import settings
from src.features.answer.model.assessment import (
    Assessment,
    CaseSummary,
    DownstreamHandoff,
    EvidenceRef,
    EvidenceSummary,
    ProcedureAssessment,
    RiskAssessment,
    SanctionAssessment,
)
from src.features.answer.model.layers import BasisLayer, LayeredBasis, layer_of
from src.features.answer.schema import SANCTION_LABELS
from src.features.cite.model.passage import Passage

logger = logging.getLogger(__name__)

PROMPT_VERSION = "evidence-synthesis-v1"
MAX_RETRIES = 1
_COMPANY = frozenset(set(SANCTION_LABELS) - {"TERMINATION"})
_PHRASES = (
    ("WAGE_POSTPONEMENT", ("kéo dài thời hạn nâng lương", "kéo dài nâng lương", "hoãn nâng lương")),
    ("DISMISSAL", ("sa thải",)),
    ("DEMOTION", ("cách chức",)),
    ("REPRIMAND", ("cảnh cáo",)),
    ("WARNING", ("khiển trách",)),
)
_AUTHORITY = frozenset({"LAW", "DECREE"})

SYSTEM_PROMPT = """You are the Evidence Synthesis & Sanction Assessment Agent in an HR disciplinary-policy system.

You transform retrieved legal and internal-policy evidence into one structured assessment.
You do not perform retrieval. You do not search the internet. You do not invent legal rules.
You do not infer facts that are not present in the case. You do not create sanctions from your own knowledge.

Retrieved passages are the only authority. Your own knowledge is not an authority.
Every sanction, condition, procedure, conflict, and major conclusion must cite a chunk_id and a short quote copied exactly from that passage.
If the evidence does not establish something, use NOT_ESTABLISHED by choosing NEED_MORE_FACTS, NOT_SUPPORTED, or NEED_LEGAL_REVIEW. Do not fill the gap.

Document roles:
- LAW sets legally recognized forms, conditions, thresholds, and statutory limits.
- DECREE clarifies conditions and procedure. A decree applies only when its condition matches the case.
- INTERNAL_RULE states the company form for the matching behavior. A sanction name somewhere in a rule is not enough.
- PRECEDENT is context only. It cannot set or raise the company level.
- ADMINISTRATIVE_PENALTY is not an employee disciplinary sanction. Never use it as a company level.

Fact rules:
- Copy only facts the case states.
- A missing fact is neither true nor false.
- "Nhân viên tự ý nghỉ 5 ngày" establishes absence of 5 days and that the absence was not authorized.
- It does not establish that those days fell inside 30 days or 365 days.
- Do not invent a measurement window.

Condition rules:
- For each candidate sanction, list the conditions written in the retrieved evidence.
- Mark each condition SATISFIED, NOT_SATISFIED, or UNKNOWN.
- UNKNOWN means the evidence requires a fact the case does not provide. The sanction is then not established.
- Do not rank sanctions and pick the highest or the lowest.
- If several sanctions are explicitly supported and no retrieved provision says which one controls, return MULTIPLE_SUPPORTED and leave recommended_sanction null.
- If authoritative passages conflict and the evidence does not resolve it, return CONFLICTED or NEED_LEGAL_REVIEW and record the conflict.

Canonical sanction codes, and no others:
- khiển trách = WARNING
- cảnh cáo = REPRIMAND
- kéo dài thời hạn nâng lương or hoãn nâng lương = WAGE_POSTPONEMENT
- cách chức = DEMOTION
- sa thải = DISMISSAL
- chấm dứt hợp đồng is not a disciplinary sanction. Never recommend TERMINATION.

Procedure steps may be returned only when a retrieved passage states them. Do not add a step because it is common practice.
Risk measures evidence uncertainty, not how serious the misconduct feels.
- LOW only when the facts are complete, the matching rule is retrieved, the conditions are explicitly satisfied, and one sanction is cited.
- MEDIUM when one sanction is supported but a secondary fact or a procedure citation is incomplete, or more than one provision may apply.
- HIGH when a required fact is missing, the internal rule is missing, a condition is UNKNOWN, sources conflict, or the level cannot safely be recommended.

Write reason, notes, and questions in Vietnamese.
Return one JSON object matching the schema. recommended_sanction is a canonical code or null.
"""


def unavailable_assessment(facts: dict[str, str], reason: str) -> Assessment:
    """Assessment used when the model cannot be read. It recommends no level."""
    return Assessment(
        case_summary=CaseSummary(violation="", facts=dict(facts), missing_facts=[]),
        evidence_summary=EvidenceSummary(),
        sanction_assessment=SanctionAssessment(
            status="NEED_LEGAL_REVIEW",
            recommended_sanction=None,
            reason=reason,
        ),
        procedure_assessment=ProcedureAssessment(),
        risk_assessment=RiskAssessment(level="HIGH", reasons=[reason]),
        downstream_handoff=DownstreamHandoff(needs_legal_review=True),
    )


async def synthesize(message: CaseHandoff, layered: LayeredBasis) -> Assessment:
    """Read one handoff. A missing key or a bad payload leaves the level unset."""
    if not settings.OPENAI_API_KEY:
        return unavailable_assessment(message.facts, "Chưa có mô hình tổng hợp. Chưa chốt mức từ các đoạn đã lấy.")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _payload(message, layered)},
    ]
    last_error = "invalid_assessment"
    for attempt in range(MAX_RETRIES + 1):
        try:
            parsed = await _complete(messages, attempt)
            return guard(parsed, _passages(layered))
        except Exception as exc:
            last_error = type(exc).__name__
            logger.warning("evidence synthesis attempt %s failed: %s", attempt + 1, last_error)
    reason = f"Không đọc được bản tổng hợp ({last_error}). Chưa chốt mức."
    return unavailable_assessment(message.facts, reason)


def guard(assessment: Assessment, passages: list[Passage]) -> Assessment:
    """Drop conclusions whose quotes are not in the retrieved chunks."""
    index = {_chunk_key(passage.chunk_id): passage for passage in passages}
    status = assessment.sanction_assessment.status
    level = _canonical(assessment.sanction_assessment.recommended_sanction)
    evidence = _valid_refs(assessment.sanction_assessment.evidence, index)
    risk = assessment.risk_assessment.level
    reason = assessment.sanction_assessment.reason.strip() or "Chưa có nhận định từ các đoạn đã lấy."
    if status == "SUPPORTED":
        if level is None or risk == "HIGH" or not _grounded(level, evidence, index):
            status = "NEED_LEGAL_REVIEW"
            level = None
            risk = "HIGH"
            reason = f"{reason} Trích dẫn không đủ để chốt một mức."
    elif status == "MULTIPLE_SUPPORTED":
        level = None
        risk = "HIGH" if risk == "HIGH" else "MEDIUM"
    else:
        level = None
        risk = "HIGH"
    can_recommend = status == "SUPPORTED" and level is not None and risk in {"LOW", "MEDIUM"}
    return assessment.model_copy(
        update={
            "sanction_assessment": assessment.sanction_assessment.model_copy(
                update={"status": status, "recommended_sanction": level, "reason": reason, "evidence": evidence}
            ),
            "risk_assessment": assessment.risk_assessment.model_copy(update={"level": risk}),
            "downstream_handoff": DownstreamHandoff(
                can_recommend=can_recommend,
                can_finalize=False,
                needs_clarification=status == "NEED_MORE_FACTS" or bool(assessment.evidence_gaps),
                needs_legal_review=status in {"CONFLICTED", "NEED_LEGAL_REVIEW"} or not can_recommend,
            ),
        }
    )


def _grounded(level: str, evidence: list[EvidenceRef], index: dict[str, Passage]) -> bool:
    rule_named = False
    authority = False
    for ref in evidence:
        passage = index.get(_chunk_key(ref.chunk_id))
        if passage is None:
            continue
        role = _role(passage)
        if role == "INTERNAL_RULE" and _phrase_in(level, ref.quote):
            rule_named = True
        if role in _AUTHORITY:
            authority = True
    return rule_named and authority


def _valid_refs(refs: list[EvidenceRef], index: dict[str, Passage]) -> list[EvidenceRef]:
    kept: list[EvidenceRef] = []
    for ref in refs:
        passage = index.get(_chunk_key(ref.chunk_id))
        quote = ref.quote.strip()
        if passage is None or not quote or quote not in passage.content:
            continue
        if _role(passage) in {"PRECEDENT", "ADMINISTRATIVE_PENALTY"}:
            continue
        kept.append(EvidenceRef(chunk_id=str(passage.chunk_id), quote=quote))
    return kept


def _role(passage: Passage) -> str:
    layer = layer_of(passage.policy_type, passage.policy_code, passage.policy_name)
    if layer == BasisLayer.INTERNAL_RULE:
        return "INTERNAL_RULE"
    if layer == BasisLayer.PRECEDENT:
        return "PRECEDENT"
    if layer == BasisLayer.INSPECTION_RISK:
        return "ADMINISTRATIVE_PENALTY"
    if passage.policy_type == "LAW":
        return "LAW"
    return "DECREE"


def _phrase_in(level: str, text: str) -> bool:
    folded = text.casefold()
    return any(phrase in folded for level_name, phrases in _PHRASES if level_name == level for phrase in phrases)


def _canonical(value: str | None) -> str | None:
    if not value:
        return None
    token = value.strip()
    if token.upper() in _COMPANY:
        return token.upper()
    folded = token.casefold()
    hits = [level for level, phrases in _PHRASES if folded in phrases]
    if len(hits) == 1:
        return hits[0]
    return None


def _payload(message: CaseHandoff, layered: LayeredBasis) -> str:
    body = {
        "case": {
            "description": message.description,
            "event_date": message.incident_date.isoformat(),
            "employee_name": message.employee_name,
            "facts": dict(message.facts),
            "fact_lines": list(message.fact_lines),
        },
        "retrieval": {
            "law": [_row(item) for item in layered.legal_basis if item.policy_type == "LAW"],
            "decree": [_row(item) for item in layered.legal_basis if item.policy_type != "LAW"],
            "internal_rule": [_row(item) for item in layered.internal_rule],
            "precedent": [_row(item) for item in layered.precedent],
            "administrative_penalty": [_row(item) for item in layered.inspection_risk],
        },
    }
    return json.dumps(body, ensure_ascii=False)


def _row(passage: Passage) -> dict[str, str]:
    return {
        "chunk_id": str(passage.chunk_id),
        "document_id": passage.policy_code,
        "document_type": passage.policy_type or "",
        "content": passage.content,
    }


def _passages(layered: LayeredBasis) -> list[Passage]:
    return [
        *layered.legal_basis,
        *layered.internal_rule,
        *layered.precedent,
        *layered.inspection_risk,
    ]


def _chunk_key(value: UUID | str) -> str:
    try:
        return str(UUID(str(value)))
    except ValueError:
        return str(value)


async def _complete(messages: list[dict[str, str]], attempt: int) -> Assessment:
    prompt = list(messages)
    if attempt:
        prompt.append(
            {
                "role": "user",
                "content": "The previous response did not match the schema. Return one valid assessment.",
            }
        )
    model = ChatOpenAI(
        model=settings.MODEL_NAME,
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
        timeout=45,
        max_retries=0,
    )
    structured = model.with_structured_output(Assessment, method="json_schema")
    parsed = await structured.ainvoke(prompt)
    if isinstance(parsed, Assessment):
        return parsed
    if isinstance(parsed, dict):
        return Assessment.model_validate(parsed)
    raise TypeError("synthesis returned an unexpected payload")
