"""Synthetic instruments exercise the general contract, without a conduct lookup table."""

from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agents.handoff import CaseHandoff, CitedPassage
from src.features.answer.model import answers
from src.features.answer.model.assessment import (
    ApplicableRule,
    Assessment,
    CaseSummary,
    EvidenceRef,
    IssuanceCheck,
    RiskAssessment,
    RuleCondition,
    SanctionAssessment,
    SeverityAssessment,
)
from src.features.answer.model.conversation import assessment_reply
from src.features.answer.model.decide import DecisionInput, decide
from src.features.answer.model.layers import split_passages
from src.features.answer.model.report import render_report
from src.features.answer.model.rubric import ISSUANCE_CATEGORIES, condition_result
from src.features.answer.model.synthesis import guard, unavailable_assessment
from src.features.cite.model.passage import Passage


def _example():
    facts = {
        "conduct": "không ghi nhận lượt bàn giao thiết bị",
        "minutes_made": "false",
        "explanation_requested": "false",
    }
    law = Passage(
        uuid4(),
        uuid4(),
        "Hình thức khiển trách được xem xét nếu có lỗi trong bàn giao.",
        "A",
        None,
        None,
        0.9,
        "LAW",
        "SYNTHETIC-L",
        "Luật giả lập kiểm thử",
        retrieval_status="OK",
    )
    rule = Passage(
        uuid4(),
        uuid4(),
        "Không ghi nhận bàn giao do có lỗi thì khiển trách.",
        "B",
        None,
        None,
        0.9,
        "INTERNAL_RULE",
        "SYNTHETIC-NQ",
        "Nội quy giả lập kiểm thử",
        retrieval_status="OK",
    )
    refs = [EvidenceRef(chunk_id=str(item.chunk_id), quote=item.content) for item in (law, rule)]
    raw = Assessment(
        case_summary=CaseSummary(violation=facts["conduct"], facts=facts),
        sanction_assessment=SanctionAssessment(
            status="SUPPORTED",
            recommended_sanction="WARNING",
            reason="Tình tiết khớp điều khoản bàn giao.",
            evidence=refs,
        ),
        risk_assessment=RiskAssessment(level="LOW"),
        applicable_rules=[
            ApplicableRule(
                rule_id=str(item.chunk_id),
                description="Nguồn giả lập",
                document_type=item.policy_type,
                supports_sanction="WARNING",
                evidence=[ref],
                conditions=[
                    RuleCondition(
                        fact="conduct",
                        fact_value=facts["conduct"],
                        required="Có lỗi bàn giao",
                        result="SATISFIED",
                        evidence=[ref],
                    )
                ],
            )
            for item, ref in zip((law, rule), refs, strict=True)
        ],
    )
    return facts, [law, rule], raw


def _decide(facts, passages, assessment):
    return decide(DecisionInput("UNSEEN_FAMILY", facts, split_passages(passages)), assessment)


def _check(facts, passages, *, category="PROCEDURE", result="NOT_SATISFIED", effect="PROCEDURE"):
    return IssuanceCheck(
        category=category,
        requirement="Điều kiện giả lập cần đối chiếu",
        result=result,
        effect=effect,
        fact_values={"minutes_made": facts["minutes_made"]},
        evidence=[EvidenceRef(chunk_id=str(passages[0].chunk_id), quote=passages[0].content)],
        next_action="Hoàn thiện hồ sơ thủ tục đã được đối chiếu.",
    )


def test_missing_procedure_keeps_grounded_proposal_and_reports_actions():
    facts, passages, raw = _example()
    raw.rubric_reasoning.issuance_checks = [_check(facts, passages)]
    accepted = guard(raw, passages, facts=facts)
    assert _decide(facts, passages, accepted).sanction_type == "WARNING"
    assert accepted.issuance.status == "NEEDS_PROCEDURE"
    assert len({item.category for item in accepted.issuance.checks}) == 5
    assert not accepted.downstream_handoff.can_finalize
    reply = assessment_reply(accepted, _decide(facts, passages, accepted), split_passages(passages))
    assert "tôi đề xuất mức khiển trách" in reply and "Trước khi ban hành" in reply
    assert "xác suất kết luận đúng" in reply and "Mở biên bản" not in reply


def test_heading_and_body_from_same_chunk_bind_sanction():
    facts, passages, raw = _example()
    rule = replace(
        passages[1], content="Không ghi nhận bàn giao do có lỗi.", section_title="Áp dụng hình thức Khiển trách"
    )
    body = EvidenceRef(chunk_id=str(rule.chunk_id), quote=rule.content)
    heading = EvidenceRef(chunk_id=str(rule.chunk_id), quote=rule.section_title, source="HEADING")
    raw.sanction_assessment.evidence = [raw.sanction_assessment.evidence[0], heading, body]
    raw.applicable_rules[1].evidence = [heading, body]
    raw.applicable_rules[1].conditions[0].evidence = [body]
    accepted = guard(raw, [passages[0], rule], facts=facts)
    assert accepted.downstream_handoff.can_recommend
    assert accepted.confidence.score == 100
    assert not accepted.confidence.calibrated
    reply = assessment_reply(
        accepted, _decide(facts, [passages[0], rule], accepted), split_passages([passages[0], rule])
    )
    assert f"“{rule.section_title}”; “{rule.content}”" in reply


@pytest.mark.parametrize("attack", ["other_chunk", "invented_heading", "heading_only", "heading_as_content"])
def test_forged_or_unbound_heading_does_not_unlock_proposal(attack):
    facts, passages, raw = _example()
    rule = replace(
        passages[1], content="Không ghi nhận bàn giao do có lỗi.", section_title="Áp dụng hình thức Khiển trách"
    )
    body = EvidenceRef(chunk_id=str(rule.chunk_id), quote=rule.content)
    heading = EvidenceRef(chunk_id=str(rule.chunk_id), quote=rule.section_title, source="HEADING")
    if attack == "other_chunk":
        heading.chunk_id = str(uuid4())
    elif attack == "invented_heading":
        heading.quote = "Cảnh cáo rồi sa thải"
    elif attack == "heading_as_content":
        heading.source = "CONTENT"
    refs = [heading] if attack == "heading_only" else [heading, body]
    raw.sanction_assessment.evidence = [raw.sanction_assessment.evidence[0], *refs]
    raw.applicable_rules[1].evidence = refs
    raw.applicable_rules[1].conditions[0].evidence = [body]
    accepted = guard(raw, [passages[0], rule], facts=facts)
    assert not accepted.downstream_handoff.can_recommend
    assert accepted.confidence.score < 50


def test_or_alternative_unknown_does_not_block_proven_branch_or_reask():
    facts, passages, raw = _example()
    for rule in raw.applicable_rules:
        rule.conditions[0].alternative_group = "branch_a"
        rule.conditions.append(
            rule.conditions[0].model_copy(
                update={
                    "alternative_group": "branch_b",
                    "fact": "unused_fact",
                    "fact_value": "",
                    "result": "UNKNOWN",
                }
            )
        )
    accepted = guard(raw, passages, facts=facts)
    assert accepted.downstream_handoff.can_recommend
    assert "unused_fact" not in accepted.case_summary.missing_facts


def test_unknown_mandatory_fact_blocks_and_survives_in_missing_questions():
    facts, passages, raw = _example()
    raw.applicable_rules[1].conditions.append(
        raw.applicable_rules[1]
        .conditions[0]
        .model_copy(
            update={
                "fact": "fault_verified",
                "fact_value": "",
                "result": "UNKNOWN",
            }
        )
    )
    accepted = guard(raw, passages, facts=facts)
    assert accepted.sanction_assessment.status == "NEED_MORE_FACTS"
    assert "fault_verified" in accepted.case_summary.missing_facts
    assert not accepted.downstream_handoff.can_recommend


@pytest.mark.parametrize("result", ["NOT_SATISFIED", "CONFLICTED"])
def test_negative_substantive_condition_blocks_even_with_perfect_quotes(result):
    facts, passages, raw = _example()
    raw.applicable_rules[1].conditions[0].result = result
    accepted = guard(raw, passages, facts=facts)
    assert not accepted.downstream_handoff.can_recommend
    assert accepted.confidence.score < 50


def test_issuance_condition_inside_rule_is_separate_from_content_support():
    facts, passages, raw = _example()
    raw.applicable_rules[1].conditions.append(
        raw.applicable_rules[1]
        .conditions[0]
        .model_copy(
            update={
                "scope": "ISSUANCE",
                "fact": "meeting_date",
                "fact_value": "",
                "result": "UNKNOWN",
            }
        )
    )
    accepted = guard(raw, passages, facts=facts)
    assert accepted.downstream_handoff.can_recommend
    assert "meeting_date" not in accepted.case_summary.missing_facts
    assert accepted.issuance.status == "NEEDS_VERIFICATION"


def test_unselected_alternative_does_not_block_or_lower_source_role_checks():
    facts, passages, raw = _example()
    raw.applicable_rules.append(
        raw.applicable_rules[1].model_copy(
            update={
                "selected": False,
                "conditions": [RuleCondition(fact="not_used", required="Other branch", result="UNKNOWN")],
            }
        )
    )
    assert guard(raw, passages, facts=facts).downstream_handoff.can_recommend


@pytest.mark.parametrize(
    "effect,expected,can_recommend",
    [
        ("TEMPORARY_BLOCK", "TEMPORARILY_BLOCKED", True),
        ("LEGAL_BLOCK", "LEGALLY_BLOCKED", False),
    ],
)
def test_verified_issuance_barriers_remain_visible(effect, expected, can_recommend):
    facts, passages, raw = _example()
    raw.rubric_reasoning.issuance_checks = [_check(facts, passages, category="PROTECTION", effect=effect)]
    accepted = guard(raw, passages, facts=facts)
    assert accepted.issuance.status == expected
    assert accepted.downstream_handoff.can_recommend == can_recommend
    assert not accepted.downstream_handoff.can_finalize
    if not can_recommend:
        assert accepted.sanction_assessment.recommended_sanction is None


@pytest.mark.parametrize("attack", ["missing_facts", "wrong_fact_value", "fake_quote"])
def test_unverified_issuance_claim_cannot_assert_ready_or_legal_barrier(attack):
    facts, passages, raw = _example()
    check = _check(facts, passages, category="PROTECTION", effect="LEGAL_BLOCK")
    if attack == "missing_facts":
        check.fact_values = {}
    elif attack == "wrong_fact_value":
        check.fact_values = {"minutes_made": "invented"}
    else:
        check.evidence[0].quote = "Invented protection"
    raw.rubric_reasoning.issuance_checks = [check]
    accepted = guard(raw, passages, facts=facts)
    assert accepted.issuance.status == "NEEDS_VERIFICATION"
    assert accepted.issuance.checks[0].result == "UNKNOWN"


def test_all_checks_satisfied_still_requires_human_approval():
    facts, passages, raw = _example()
    raw.rubric_reasoning.issuance_checks = [
        _check(facts, passages, category=category, result="SATISFIED") for category in ISSUANCE_CATEGORIES
    ]
    accepted = guard(raw, passages, facts=facts)
    assert accepted.issuance.status == "READY_FOR_HUMAN_REVIEW"
    assert accepted.issuance.human_approval_required
    assert not accepted.downstream_handoff.can_finalize


def test_severity_never_changes_sanction_and_requires_evidence():
    facts, passages, raw = _example()
    for score in (1, 5):
        raw.rubric_reasoning.severity = SeverityAssessment(
            score=score,
            reason="Mô tả tác động giả lập.",
            fact_keys=["conduct"],
            evidence=raw.sanction_assessment.evidence,
        )
        accepted = guard(raw, passages, facts=facts)
        assert _decide(facts, passages, accepted).sanction_type == "WARNING"
        assert accepted.rubric_reasoning.severity.score == score
    raw.rubric_reasoning.severity.evidence = []
    assert guard(raw, passages, facts=facts).rubric_reasoning.severity.score is None


def test_source_health_changes_support_index_without_claiming_probability():
    facts, passages, raw = _example()
    good = guard(raw, passages, facts=facts)
    unassessed = guard(raw, [replace(item, retrieval_status="UNASSESSED") for item in passages], facts=facts)
    incomplete = guard(
        raw,
        [replace(item, retrieval_status="INCOMPLETE", evidence_gaps=("MISSING_DEPENDENCY",)) for item in passages],
        facts=facts,
    )
    assert good.confidence.score > unassessed.confidence.score > incomplete.confidence.score
    assert unassessed.downstream_handoff.can_recommend
    assert not incomplete.downstream_handoff.can_recommend
    assert good.confidence.score_kind == "EVIDENCE_SUPPORT_INDEX" and not good.confidence.calibrated


def test_model_risk_rating_is_not_a_self_confidence_gate():
    facts, passages, raw = _example()
    raw.risk_assessment.level = "HIGH"
    accepted = guard(raw, passages, facts=facts)
    assert accepted.downstream_handoff.can_recommend
    assert accepted.risk_assessment.level == "HIGH"
    assert accepted.downstream_handoff.needs_legal_review
    assert accepted.confidence.score <= 60
    assert accepted.issuance.status == "NEEDS_VERIFICATION"


@pytest.mark.parametrize("code", ["REPRIMAND", "cảnh cáo", "TERMINATION", "FINE", "invented"])
def test_unsupported_legacy_or_invented_level_is_not_a_new_proposal(code):
    facts, passages, raw = _example()
    raw.sanction_assessment.recommended_sanction = code
    accepted = guard(raw, passages, facts=facts)
    assert not accepted.downstream_handoff.can_recommend
    assert _decide(facts, passages, accepted).sanction_type is None


def test_provider_error_is_zero_support_and_not_a_substantive_conclusion():
    failed = unavailable_assessment({}, "synthetic provider failure")
    assert failed.confidence.score == 0
    assert failed.operational_status == "LLM_FAILED"
    assert failed.issuance.status == "NEEDS_VERIFICATION"


def test_existing_form_receives_scores_and_issuance_actions_without_new_frontend_fields():
    from src.features.assessment.agent import compose
    from tests.test_assessment_form import _source

    facts, passages, raw = _example()
    raw.rubric_reasoning.issuance_checks = [_check(facts, passages)]
    accepted = guard(raw, passages, facts=facts)
    source = _source(confirmed=True, sanction="WARNING")
    source = replace(source, answer=source.answer.model_copy(update=answers.evaluation_fields(accepted)))
    sections, _ = compose(source)
    assert "Điểm hỗ trợ của căn cứ: 100/100" in sections.handling_proposal.rationale
    assert "Cần hoàn thiện thủ tục" in sections.assessment.narrative
    assert sections.handling_proposal.confidence == "HIGH"
    assert any(step.text == raw.rubric_reasoning.issuance_checks[0].next_action for step in sections.next_steps)


def test_source_manifest_normalizes_uuid_case_and_fingerprints_verified_input():
    from hashlib import sha256

    facts, passages, raw = _example()
    for ref in raw.sanction_assessment.evidence:
        ref.chunk_id = ref.chunk_id.upper()
    accepted = guard(raw, passages, facts=facts)
    assert accepted.downstream_handoff.can_recommend
    assert len(accepted.confidence.sources) == 2
    assert accepted.confidence.sources[0].content_sha256 == sha256(passages[0].content.encode()).hexdigest()
    assert accepted.confidence.sources[0].citation_integrity_score == 100


def test_report_contains_score_components_and_versioned_heading_references():
    facts, passages, raw = _example()
    accepted = guard(raw, passages, facts=facts)
    message = CaseHandoff(
        incident_date=date(2026, 10, 1),
        employee_name="Synthetic",
        family="UNSEEN_FAMILY",
        description="Synthetic",
        facts=facts,
        agent_run_id=uuid4(),
        missing_internal_rule=False,
        passages=[
            CitedPassage(
                **{
                    name: getattr(item, name)
                    for name in (
                        "chunk_id",
                        "policy_version_id",
                        "content",
                        "article",
                        "clause",
                        "point",
                        "score",
                        "policy_type",
                        "policy_code",
                        "policy_name",
                    )
                }
            )
            for item in passages
        ],
    )
    report = render_report(message, accepted)
    assert "Điểm hỗ trợ của căn cứ" in report and "citation_integrity" in report
    assert "Trạng thái ban hành" in report and str(passages[0].policy_version_id) in report


@pytest.mark.asyncio
async def test_stored_answer_reloads_structured_evaluation_without_new_model_call(monkeypatch):
    facts, passages, raw = _example()
    accepted = guard(raw, passages, facts=facts)
    view = SimpleNamespace(model_copy=lambda *, update: SimpleNamespace(**update))
    recommendation = SimpleNamespace(id=uuid4(), agent_run_id=uuid4())
    session = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(run_metadata={"synthesis_assessment": accepted.model_dump(mode="json")})
        )
    )
    monkeypatch.setattr(answers, "latest_recommendation", AsyncMock(return_value=recommendation))
    monkeypatch.setattr(answers, "list_citation_rows", AsyncMock(return_value=[]))
    monkeypatch.setattr(answers, "to_answer_view", lambda *args: view)
    monkeypatch.setattr(answers, "attach_packet", AsyncMock(side_effect=lambda session, result: result))
    result = await answers.load_stored(session, SimpleNamespace(id=uuid4(), status="ANALYZED"))
    assert result.confidence.score == accepted.confidence.score
    assert result.issuance.status == accepted.issuance.status


@pytest.mark.parametrize(
    "values,expected",
    [
        (["SATISFIED", "UNKNOWN"], "UNKNOWN"),
        (["SATISFIED", "NOT_SATISFIED"], "NOT_SATISFIED"),
        (["SATISFIED", "CONFLICTED"], "CONFLICTED"),
    ],
)
def test_mandatory_conjunction_is_conservative(values, expected):
    conditions = [RuleCondition(fact="f", required="r", result=value) for value in values]
    assert condition_result(conditions) == expected
