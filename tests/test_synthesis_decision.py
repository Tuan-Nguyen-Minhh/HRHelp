"""The original chat format carries a decision whenever retrieval can support one."""

import json
from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from src.agents.handoff import CaseHandoff
from src.core.config import settings
from src.features.answer.model.agent import build_recommend_agent
from src.features.answer.model.conversation import assessment_reply
from src.features.answer.model.synthesis import guard, synthesize
from tests.test_answer import _ART_124, _READY, _cited, _decide, _layered, _passage, _supported


def _example():
    law = _passage("LAW", "SYNTHETIC-L", "Luật kiểm thử", _ART_124)
    rule = _passage("INTERNAL_RULE", "SYNTHETIC-NQ", "Nội quy kiểm thử", "Không ghi nhận bàn giao thì khiển trách.")
    message = CaseHandoff(
        incident_date=date(2026, 10, 15),
        family="UNSEEN_FAMILY",
        facts=_READY,
        passages=[_cited(law), _cited(rule)],
        missing_internal_rule=False,
        agent_run_id=uuid4(),
    )
    return law, rule, message


def test_unknown_condition_keeps_level_and_original_chat_format():
    law, rule, _message = _example()
    raw = _supported("WARNING", law, rule)
    raw.applicable_rules[1].conditions[0].result = "UNKNOWN"
    accepted = guard(raw, [law, rule], facts=_READY)
    decision = _decide(_layered(law, rule), assessment=accepted)
    reply = assessment_reply(accepted, decision, _layered(law, rule))

    assert decision.sanction_type == "WARNING"
    assert decision.risk_level == "HIGH"
    assert not accepted.downstream_handoff.can_recommend
    assert not accepted.downstream_handoff.can_finalize
    assert reply.startswith("Với các tình tiết đã xác nhận, tôi đề xuất mức khiển trách")
    assert "chưa đủ căn cứ" not in reply.lower()
    assert "BIÊN BẢN" not in reply and "NEED_LEGAL_REVIEW" not in reply
    assert "Căn cứ hỗ trợ mức xử lý này được đánh giá" in reply
    assert "Trước khi ban hành" in reply


@pytest.mark.asyncio
async def test_synthesis_repairs_an_empty_decision_with_existing_retrieval(monkeypatch):
    law, rule, message = _example()
    unfinished = _supported("WARNING", law, rule)
    unfinished.sanction_assessment.status = "NEED_MORE_FACTS"
    unfinished.sanction_assessment.recommended_sanction = None
    finished = _supported("WARNING", law, rule)
    calls = []

    async def complete(messages, attempt, model_name):
        calls.append((list(messages), attempt))
        return unfinished if len(calls) == 1 else finished

    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test")
    monkeypatch.setattr(settings, "FALLBACK_MODEL_NAME", "")
    monkeypatch.setattr("src.features.answer.model.synthesis._complete", complete)
    accepted = await synthesize(message, _layered(law, rule))

    assert accepted.sanction_assessment.recommended_sanction == "WARNING"
    assert len(calls) == 2 and calls[1][1] == 1
    assert "Bản tổng hợp chưa có quyết định mức xử lý hợp lệ" in calls[1][0][-1]["content"]


@pytest.mark.asyncio
async def test_empty_retrieval_skips_synthesis_and_is_the_insufficient_basis_reply(monkeypatch):
    _law, _rule, message = _example()
    message = message.model_copy(update={"passages": [], "missing_internal_rule": True})
    complete = AsyncMock()
    monkeypatch.setattr("src.features.answer.model.agent.synthesize", complete)
    state = await build_recommend_agent().ainvoke({"handoff": message})

    complete.assert_not_awaited()
    assert state["draft"].decision.sanction_type is None
    assert "Chưa có đủ căn cứ để đưa ra mức xử lý" in state["draft"].chat_message


def test_inapplicable_sources_produce_a_no_discipline_decision_instead_of_missing_data():
    law, rule, _message = _example()
    raw = _supported("WARNING", law, rule)
    raw.sanction_assessment.status = "NOT_SUPPORTED"
    raw.sanction_assessment.recommended_sanction = None
    raw.sanction_assessment.reason = "Điều khoản đang xét không áp dụng cho vụ việc này."
    accepted = guard(raw, [law, rule], facts=_READY)
    reply = assessment_reply(accepted, _decide(_layered(law, rule), assessment=accepted), _layered(law, rule))

    assert reply.startswith("Tôi đề xuất chưa áp dụng kỷ luật")
    assert "chưa đủ căn cứ" not in reply.lower()
    assert "Điều khoản đang xét không áp dụng" in reply


@pytest.mark.asyncio
@pytest.mark.parametrize("reasoning_effort", ["low", "high"])
async def test_truncated_completion_keeps_reasoning_and_accepts_compact_output(monkeypatch, reasoning_effort):
    from src.features.answer.model import synthesis
    from src.services import chat_client

    law, rule, message = _example()
    finished = synthesis.SynthesisAssessment.model_validate(_supported("WARNING", law, rule).model_dump())
    finished.case_summary.facts = {}
    original = chat_client.ChatOpenAI
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        truncated = len(requests) == 1
        return httpx.Response(
            200,
            json={
                "id": "length-regression",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-flash",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "length" if truncated else "stop",
                        "message": {
                            "role": "assistant",
                            "content": '{"case_summary":' if truncated else finished.model_dump_json(),
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 12000 if truncated else 500,
                    "total_tokens": 12100 if truncated else 600,
                },
            },
        )

    monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test")
    monkeypatch.setattr(settings, "FALLBACK_MODEL_NAME", "")
    monkeypatch.setattr(settings, "SYNTHESIS_MAX_TOKENS", 12000)
    monkeypatch.setattr(settings, "SYNTHESIS_REASONING_EFFORT", reasoning_effort)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(chat_client, "ChatOpenAI", lambda **kwargs: original(http_async_client=client, **kwargs))
        accepted = await synthesize(message, _layered(law, rule))

    assert len(requests) == 2
    assert requests[0]["max_tokens"] == 12000 and requests[0]["thinking"]["type"] == "enabled"
    assert requests[1]["max_tokens"] == 24000 and requests[1]["thinking"]["type"] == "enabled"
    assert all(request["reasoning_effort"] == reasoning_effort for request in requests)
    assert all("max_completion_tokens" not in request for request in requests)
    assert all(rule.content in json.dumps(request["messages"], ensure_ascii=False) for request in requests)
    assert accepted.operational_status == "OK"
    assert accepted.sanction_assessment.recommended_sanction == "WARNING"
    assert all(accepted.case_summary.facts[key] == value for key, value in _READY.items())
    assert accepted.case_summary.facts["incident_date"] == message.incident_date.isoformat()


def test_length_retry_keeps_a_bounded_output_budget(monkeypatch):
    from src.features.answer.model.synthesis import _output_budget

    monkeypatch.setattr(settings, "SYNTHESIS_MAX_TOKENS", 32000)
    assert _output_budget(length_retry=True) == 32000
