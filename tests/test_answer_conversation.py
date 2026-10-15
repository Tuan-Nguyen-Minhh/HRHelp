"""Chat shows a guarded proposal and sources; reports and traces stay separate."""

from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.features.answer.model.assessment import EvidenceRef
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
    assert accepted.sanction_assessment.recommended_sanction == "WARNING"
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
    assert "tôi đề xuất mức khiển trách" in reply
    assert "Trước khi ban hành" in reply


def test_provider_failure_does_not_show_technical_errors_or_make_up_a_level():
    law, rule, _assessment = _example()
    failed = unavailable_assessment(_READY, "deepseek-flash: OpenAITimeoutError")
    reply = assessment_reply(failed, _decide(_layered(law, rule), assessment=failed), _layered(law, rule))
    assert "chưa hoàn tất việc tổng hợp" in reply
    assert "OpenAITimeoutError" not in reply and "deepseek" not in reply
    assert "tôi đề xuất mức" not in reply


def test_low_support_reply_links_level_score_limits_and_actions_without_mutating_assessment():
    law, rule, assessment = _example()
    annotation = "Tình tiết đã có nhưng việc áp dụng điều kiện chưa được chứng minh bằng trích dẫn phù hợp."
    assessment.sanction_assessment.reason = "Hành vi được xem xét theo điều khoản bàn giao trong nội quy. " + annotation
    assessment.confidence.score, assessment.confidence.label = 49, "LOW"
    assessment.downstream_handoff.can_recommend = False
    assessment.risk_assessment.level = "HIGH"
    assessment.risk_assessment.reasons = [
        "Có đủ căn cứ pháp luật và nội quy cho hình thức đề xuất.",
        "Chưa lập biên bản sự việc nên trình tự thủ tục chưa hoàn tất.",
    ]
    assessment.issuance.next_actions = [
        "Hoàn tất xác minh căn cứ và điều kiện của mức xử lý đề xuất.",
        "Bổ sung ngày dự kiến ban hành quyết định.",
        "Lập biên bản sự việc và ghi nhận bản giải trình.",
    ]
    before = assessment.model_dump()
    reply = assessment_reply(assessment, _decide(_layered(law, rule), assessment=assessment), _layered(law, rule))
    opening = reply.split("\n\n", 1)[0]

    assert opening.index("mức khiển trách") < opening.index("49/100 (thấp)")
    assert "nên cần kiểm chứng thêm" in opening
    assert annotation not in reply
    assert "kiểm tra trích dẫn chứng minh điều kiện áp dụng" in reply
    assert "Có đủ căn cứ pháp luật" not in reply
    assert "Hiện tại, chưa lập biên bản" in reply
    assert ".;" not in reply and "cần chưa lập" not in reply
    assert "Trước khi ban hành quyết định, cần bổ sung ngày" in reply
    assert "lập biên bản sự việc và ghi nhận bản giải trình" in reply
    assert assessment.model_dump() == before


def test_positive_risk_with_a_qualification_keeps_the_actual_limitation():
    law, rule, assessment = _example()
    assessment.risk_assessment.level = "HIGH"
    assessment.risk_assessment.reasons = ["Có đủ căn cứ, nhưng chưa xác minh thẩm quyền ký."]
    reply = assessment_reply(assessment, _decide(_layered(law, rule), assessment=assessment), _layered(law, rule))

    assert "chưa xác minh thẩm quyền ký" in reply
    assert "Có đủ căn cứ" not in reply


def test_short_citations_show_application_clause_instead_of_only_heading_and_introduction():
    law, rule, assessment = _example()
    introduction = "Hình thức khiển trách được áp dụng trong trường hợp sau đây:"
    clause = "Không ghi nhận bàn giao khi có trách nhiệm ghi nhận thì khiển trách."
    law = replace(law, content=introduction + "\n" + clause, section_title="Áp dụng hình thức khiển trách")
    intro_ref = EvidenceRef(chunk_id=str(law.chunk_id), quote=introduction)
    heading_ref = EvidenceRef(chunk_id=str(law.chunk_id), quote=law.section_title, source="HEADING")
    clause_ref = EvidenceRef(chunk_id=str(law.chunk_id), quote=clause)
    assessment.sanction_assessment.evidence = [intro_ref, heading_ref]
    assessment.applicable_rules[0].evidence = [intro_ref, heading_ref]
    assessment.applicable_rules[0].conditions[0].evidence = [clause_ref]
    reply = assessment_reply(assessment, _decide(_layered(law, rule), assessment=assessment), _layered(law, rule))

    assert f"“{law.section_title}”; “{clause}”" in reply
    assert introduction not in reply


@pytest.mark.asyncio
async def test_chat_history_hides_agent_work_notes_and_keeps_the_final_reply(monkeypatch):
    case, conversation = SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())
    rows = [
        SimpleNamespace(
            id=uuid4(),
            role="SYSTEM",
            content="Đã xác nhận tình tiết: contract_type=...",
            created_at=datetime.now(),
            message_metadata={"kind": "facts_confirmed"},
        ),
        SimpleNamespace(
            id=uuid4(),
            role="USER",
            content="Tôi muốn đánh giá vụ việc.",
            created_at=datetime.now(),
            message_metadata={},
        ),
        *[
            SimpleNamespace(
                id=uuid4(), role="ASSISTANT", content=body, created_at=datetime.now(), message_metadata=metadata
            )
            for body, metadata in [
                ("Message đã sẵn sàng cho agent", {"kind": "handoff", "internal": True}),
                ("BIÊN BẢN I-XI", {"kind": "recommendation", "internal": True}),
                ("Mức đề xuất và căn cứ. Mở biên bản bên dưới.", {"kind": "minutes_ready"}),
            ]
        ],
    ]
    monkeypatch.setattr(controller, "require_case", AsyncMock(return_value=case))
    monkeypatch.setattr(controller, "active_conversation", AsyncMock(return_value=conversation))
    monkeypatch.setattr(controller, "list_messages", AsyncMock(return_value=rows))
    response = await controller.read_messages(case.id, SimpleNamespace(), AsyncMock(), {})
    assert [item.content for item in response.messages] == [rows[1].content, rows[-1].content]
