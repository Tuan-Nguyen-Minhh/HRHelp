"""Chat shows a guarded proposal and sources; reports and traces stay separate."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.features.answer.model.conversation import assessment_reply
from src.features.answer.model.synthesis import guard, unavailable_assessment
from src.features.clarify import controller
from tests.test_answer import _ART_124, _READY, _decide, _layered, _passage, _supported


def _example():
    law = _passage("LAW", "L", "Bộ luật Lao động", _ART_124)
    rule = _passage("INTERNAL_RULE", "NQ", "Nội quy công ty", "Người lao động nghỉ không phép thì bị khiển trách.")
    assessment = _supported("WARNING", law, rule)
    return law, rule, assessment


def test_supported_chat_is_short_and_uses_only_verified_sources():
    law, rule, assessment = _example()
    reply = assessment_reply(assessment, _decide(_layered(law, rule), assessment=assessment), _layered(law, rule))
    assert "tôi đề xuất mức khiển trách" in reply
    assert "Bộ luật Lao động" in reply and "Nội quy công ty" in reply
    assert "Điều 125" in reply
    assert str(law.chunk_id) not in reply
    assert "BIÊN BẢN" not in reply and "SUPPORTED" not in reply
    assert len(reply) < 1400


def test_model_cannot_mark_a_confirmed_fact_as_missing_or_unlock_a_level():
    law, rule, assessment = _example()
    facts = {**_READY, "incident_date": "2026-11-04"}
    raw = assessment.model_copy(
        update={
            "case_summary": assessment.case_summary.model_copy(
                update={"missing_facts": ["contract_type", "incident_date"]}
            )
        }
    )
    accepted = guard(raw, [law, rule], facts=facts)
    assert accepted.case_summary.missing_facts == []
    assert accepted.sanction_assessment.recommended_sanction is None
    assert accepted.sanction_assessment.status == "NEED_LEGAL_REVIEW"
    assert not accepted.downstream_handoff.can_recommend


def test_invalid_condition_stays_unknown_without_reasking_the_same_fact():
    law, rule, assessment = _example()
    condition = assessment.applicable_rules[0].conditions[0].model_copy(update={"fact_value": "giá trị tự bịa"})
    raw = assessment.model_copy(
        update={
            "applicable_rules": [
                assessment.applicable_rules[0].model_copy(update={"conditions": [condition]}),
                assessment.applicable_rules[1],
            ]
        }
    )
    accepted = guard(raw, [law, rule], facts=_READY)
    assert accepted.applicable_rules[0].conditions[0].result == "UNKNOWN"
    assert condition.fact not in accepted.case_summary.missing_facts
    reply = assessment_reply(accepted, _decide(_layered(law, rule), assessment=accepted), _layered(law, rule))
    assert "tôi đề xuất mức" not in reply
    assert "cần kiểm tra" in reply


def test_provider_failure_does_not_show_technical_errors_or_make_up_a_level():
    law, rule, _assessment = _example()
    failed = unavailable_assessment(_READY, "deepseek-flash: OpenAITimeoutError")
    reply = assessment_reply(failed, _decide(_layered(law, rule), assessment=failed), _layered(law, rule))
    assert "chưa hoàn tất việc tổng hợp" in reply
    assert "OpenAITimeoutError" not in reply and "deepseek" not in reply
    assert "tôi đề xuất mức" not in reply


@pytest.mark.asyncio
async def test_chat_history_hides_agent_work_notes_and_keeps_the_final_reply(monkeypatch):
    case, conversation = SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())
    rows = [
        SimpleNamespace(
            id=uuid4(), role="ASSISTANT", content=body, created_at=datetime.now(), message_metadata=metadata
        )
        for body, metadata in [
            ("Message đã sẵn sàng cho agent", {"kind": "handoff", "internal": True}),
            ("BIÊN BẢN I-XI", {"kind": "recommendation", "internal": True}),
            ("Mức đề xuất và căn cứ. Mở biên bản bên dưới.", {"kind": "minutes_ready"}),
        ]
    ]
    monkeypatch.setattr(controller, "require_case", AsyncMock(return_value=case))
    monkeypatch.setattr(controller, "active_conversation", AsyncMock(return_value=conversation))
    monkeypatch.setattr(controller, "list_messages", AsyncMock(return_value=rows))
    response = await controller.read_messages(case.id, SimpleNamespace(), AsyncMock(), {})
    assert [item.content for item in response.messages] == [rows[-1].content]
