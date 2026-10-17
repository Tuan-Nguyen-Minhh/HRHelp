"""Natural-language procedural answers must survive planner validation."""

from unittest.mock import AsyncMock

import pytest

from src.features.clarify.model.catalog import FactSpec
from src.features.clarify.model.decision import ClarifyDecision, ExtractedFact, RequestedAction, UserIntent
from src.features.clarify.model.graph import extract_node
from src.features.clarify.model.planner import PlannerResult
from src.features.clarify.model.policy import apply_decision

MESSAGE = (
    "Biên bản vụ việc: Đã lập biên bản ghi nhận sự việc vi phạm quy định bảo mật thông tin.\n\n"
    "Yêu cầu giải trình: Đã gửi văn bản yêu cầu nhân viên giải trình (thời hạn phản hồi trong 03 ngày làm việc)."
)
SPECS = (
    FactSpec("minutes_made", "Biên bản vụ việc", "Vụ việc đã được lập biên bản chưa?"),
    FactSpec("explanation_requested", "Yêu cầu giải trình", "Đã yêu cầu nhân viên giải trình chưa?"),
)


@pytest.mark.asyncio
async def test_labeled_completed_procedures_do_not_get_asked_again(monkeypatch):
    evidence = MESSAGE.split("\n\n")
    decision = ClarifyDecision(
        family="data_security",
        family_confidence=0.99,
        extracted_facts=[
            ExtractedFact(key=spec.key, value="true", confidence=0.99, evidence=proof, ambiguous=False)
            for spec, proof in zip(SPECS, evidence, strict=True)
        ],
        user_intent=UserIntent.PROVIDE_FACTS,
        requested_action=RequestedAction.COMPLETE_FACTS,
        confidence=0.99,
    )
    monkeypatch.setattr(
        "src.features.clarify.model.graph.plan_turn",
        AsyncMock(return_value=PlannerResult(decision, False, None, 1, "test")),
    )
    result = await extract_node(
        {
            "semantic": True,
            "text": MESSAGE,
            "latest_user_message": MESSAGE,
            "stored": {},
            "active_specs": list(SPECS),
            "family": "data_security",
            "pending_action": "draft_minutes",
        }
    )
    assert result["missing_keys"] == [], f"Already answered procedure facts were discarded: {result}"
    assert {key: fact.value for key, fact in result["merged"].items()} == {
        "minutes_made": "true",
        "explanation_requested": "true",
    }
    assert result["facts_locked"] is True


@pytest.mark.parametrize(
    "key,value,evidence",
    [
        ("minutes_made", "true", "Về hồ sơ này, biên bản đã được HR lập xong."),
        ("minutes_made", "true", "Đã lập biên bản, nhưng chưa nhận được giải trình của nhân viên."),
        ("explanation_requested", "true", "Yêu cầu giải trình đã được gửi; nhân viên chưa phản hồi."),
        ("minutes_made", "false", "Tình trạng biên bản: hiện bên tôi chưa lập."),
        ("explanation_requested", "false", "Về giải trình, công ty không gửi yêu cầu cho nhân viên."),
    ],
)
def test_semantic_flags_do_not_depend_on_evidence_word_order(key, value, evidence):
    decision = ClarifyDecision(
        family="data_security",
        family_confidence=0.99,
        extracted_facts=[ExtractedFact(key=key, value=value, confidence=0.99, evidence=evidence, ambiguous=False)],
        user_intent=UserIntent.PROVIDE_FACTS,
        requested_action=RequestedAction.COMPLETE_FACTS,
        confidence=0.99,
    )
    plan = apply_decision(evidence, {}, decision, active_specs=SPECS, active_family="data_security")
    assert plan.merged[key].value == value
    assert key not in plan.missing_keys and key not in plan.ambiguities


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["assistant", "memory", "fabricated"])
async def test_flags_cannot_be_grounded_only_in_assistant_or_memory_claims(monkeypatch, source):
    decision = ClarifyDecision(
        family="data_security",
        family_confidence=0.99,
        extracted_facts=[
            ExtractedFact(
                key="minutes_made", value="true", confidence=0.99, evidence="Đã lập biên bản", ambiguous=False
            )
        ],
        user_intent=UserIntent.PROVIDE_FACTS,
        requested_action=RequestedAction.COMPLETE_FACTS,
        confidence=0.99,
    )
    monkeypatch.setattr(
        "src.features.clarify.model.graph.plan_turn",
        AsyncMock(return_value=PlannerResult(decision, False, None, 1, "test")),
    )
    text = "USER: Tôi chưa cung cấp tình tiết này."
    if source == "assistant":
        text += "\nASSISTANT: Đã lập biên bản\nminutes_made: true"
    elif source == "memory":
        text += "\nSHORT_TERM_MEMORY: Đã lập biên bản\nminutes_made: true"
    result = await extract_node(
        {
            "semantic": True,
            "text": text,
            "latest_user_message": "Tôi chưa cung cấp tình tiết này.",
            "active_specs": list(SPECS),
            "family": "data_security",
            "stored": {},
        }
    )
    assert "minutes_made" not in result["merged"]
    assert "minutes_made" in result["missing_keys"]


@pytest.mark.asyncio
async def test_original_user_history_is_a_source_for_resuming_without_repeating_answers(monkeypatch):
    question = "Tôi đã cung cấp rồi, hãy tiếp tục."
    proof = MESSAGE.split("\n\n")[0]
    decision = ClarifyDecision(
        family="data_security",
        family_confidence=0.99,
        extracted_facts=[
            ExtractedFact(key="minutes_made", value="true", confidence=0.99, evidence=proof, ambiguous=False)
        ],
        user_intent=UserIntent.CONTINUE,
        requested_action=RequestedAction.COMPLETE_FACTS,
        confidence=0.99,
    )
    monkeypatch.setattr(
        "src.features.clarify.model.graph.plan_turn",
        AsyncMock(return_value=PlannerResult(decision, False, None, 1, "test")),
    )
    result = await extract_node(
        {
            "semantic": True,
            "text": MESSAGE + "\nUSER: " + question,
            "latest_user_message": question,
            "user_fact_sources": [MESSAGE, question],
            "active_specs": list(SPECS),
            "family": "data_security",
            "stored": {},
        }
    )
    assert result["merged"]["minutes_made"].value == "true"
    assert "minutes_made" not in result["missing_keys"]


@pytest.mark.asyncio
async def test_explicit_current_values_win_without_replaying_old_key_value_lines(monkeypatch):
    message = "Đã lập biên bản, yêu cầu giải trình chưa gửi."
    decision = ClarifyDecision(
        family="data_security",
        family_confidence=0.99,
        extracted_facts=[
            ExtractedFact(
                key="minutes_made", value="true", confidence=0.99, evidence="Đã lập biên bản", ambiguous=False
            )
        ],
        user_intent=UserIntent.CORRECT_FACTS,
        requested_action=RequestedAction.COMPLETE_FACTS,
        confidence=0.99,
    )
    monkeypatch.setattr(
        "src.features.clarify.model.graph.plan_turn",
        AsyncMock(return_value=PlannerResult(decision, False, None, 1, "test")),
    )
    result = await extract_node(
        {
            "semantic": True,
            "text": "USER: minutes_made: false\nUSER: " + message,
            "latest_user_message": message,
            "user_fact_sources": ["minutes_made: false", message],
            "active_specs": list(SPECS),
            "family": "data_security",
            "stored": {},
        }
    )
    assert result["merged"]["minutes_made"].value == "true"


def test_ambiguous_or_low_confidence_semantic_flag_is_still_missing():
    decision = ClarifyDecision(
        family="data_security",
        family_confidence=0.99,
        extracted_facts=[
            ExtractedFact(
                key="minutes_made", value="true", confidence=0.4, evidence="Có lẽ đã lập biên bản", ambiguous=False
            ),
            ExtractedFact(
                key="explanation_requested", value="", confidence=0.8, evidence="Không nhớ đã gửi chưa", ambiguous=True
            ),
        ],
        user_intent=UserIntent.PROVIDE_FACTS,
        requested_action=RequestedAction.COMPLETE_FACTS,
        confidence=0.99,
    )
    plan = apply_decision(
        "Có lẽ đã lập biên bản. Không nhớ đã gửi chưa", {}, decision, active_specs=SPECS, active_family="data_security"
    )
    assert plan.missing_keys == ["minutes_made", "explanation_requested"]
    assert not plan.merged
