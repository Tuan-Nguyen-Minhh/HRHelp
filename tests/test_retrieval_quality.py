"""Regression cases for source selection and the real Cohere HTTP boundary.

These fixtures verify mechanics and refusal paths, not legal-domain accuracy.
"""

import json
from dataclasses import replace
from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace

from src.core.config import settings
from src.features.answer.model.synthesis import guard, synthesize
from src.features.cite.model import pipeline
from src.features.cite.model.evidence import evidence_size, select_evidence
from src.features.cite.model.graph import handoff_node
from src.features.cite.model.query import SearchQuery, act_text
from src.features.cite.model.rerank import RerankResult, rerank
from src.features.cite.model.store import fetch_by_bm25
from src.features.cite.model.terms import search_terms
from tests.test_answer import _ART_124, _READY, _passage, _supported
from tests.test_graph_expand import graph_db  # noqa: F401


@pytest.fixture(autouse=True)
def no_live_cohere(monkeypatch):
    monkeypatch.setattr(settings, "COHERE_API_KEY", "")
    monkeypatch.setattr(settings, "RERANK_MIN_SCORE", None)
    monkeypatch.setattr(settings, "SYNTHESIS_TOKENIZER_PATH", "")


def disclosure_query():
    return SearchQuery("", date(2026, 10, 29), uuid4(), "GENERAL", [
        "Loại hợp đồng: xác định thời hạn",
        "Hành vi vi phạm: của nhân viên này",
        "Loại thông tin bị tiết lộ: mã nguồn hệ thống và tài liệu kiến trúc phần mềm",
        "Đối tượng nhận thông tin: người thuộc tổ chức đối thủ",
        "Đã lập biên bản: true",
    ], "")


def test_disclosure_terms_do_not_get_crowded_out_by_contract_facts():
    query = disclosure_query()
    terms = search_terms(query.family, query.fact_lines, query.description)
    assert {"mã nguồn", "tiết lộ", "kiến trúc phần mềm", "đối thủ"}.issubset(terms)
    assert "hợp" not in terms
    assert "hợp đồng" not in act_text(query)
    assert "của nhân viên này" not in act_text(query)
    assert "mã nguồn" in act_text(query)


def install_transport(monkeypatch, responder):
    original = httpx.AsyncClient
    calls = []

    def handle(request):
        calls.append(request)
        return responder(request)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    monkeypatch.setattr(settings, "COHERE_API_KEY", "test-secret")
    return calls


@pytest.mark.asyncio
async def test_cohere_maps_out_of_order_indices_and_preserves_verbatim_content(monkeypatch):
    first = _passage("LAW", "LAW", "Law", "Không được xử lý trong trường hợp ngoại lệ.")
    second = _passage("INTERNAL_RULE", "NQ", "Rule", "Mã nguồn phải được bảo mật.")
    calls = install_transport(monkeypatch, lambda request: httpx.Response(200, json={"results": [
        {"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.5}]}))
    result = await rerank("tiết lộ mã nguồn", [first, second])
    assert result.status == "OK"
    assert result.passages[0].chunk_id == second.chunk_id
    assert result.passages[0].content == second.content
    body = json.loads(calls[0].content)
    assert body["model"] == "rerank-v4.0-pro"
    assert body["top_n"] == 2
    assert body["max_tokens_per_doc"] == 32768
    assert json.loads(body["documents"][0])["content"] == first.content
    assert result.passages[0].score == second.score  # never overwrite RRF with probability-like values


@pytest.mark.asyncio
@pytest.mark.parametrize("results", [
    [{"index": 0, "relevance_score": 0.8}, {"index": 0, "relevance_score": 0.7}],
    [{"index": 0, "relevance_score": 0.8}],
    [{"index": -1, "relevance_score": 0.8}, {"index": 1, "relevance_score": 0.7}],
    [{"index": True, "relevance_score": 0.8}, {"index": 0, "relevance_score": 0.7}],
    [{"index": 0, "relevance_score": 1.1}, {"index": 1, "relevance_score": 0.7}],
])
async def test_invalid_cohere_results_fail_closed(monkeypatch, results):
    hits = [_passage("LAW", "L", "Law", "A"), _passage("LAW", "L", "Law", "B")]
    install_transport(monkeypatch, lambda request: httpx.Response(200, json={"results": results}))
    result = await rerank("query", hits)
    assert result.status == "FAILED"
    assert result.passages == hits


@pytest.mark.asyncio
async def test_cohere_http_failure_does_not_retry_or_log_secret(monkeypatch, caplog):
    calls = install_transport(monkeypatch, lambda request: httpx.Response(401, text="test-secret private case"))
    result = await rerank("private query", [_passage("LAW", "L", "Law", "Evidence")])
    assert len(calls) == 1
    assert result.error == "HTTP_401"
    assert "test-secret" not in caplog.text
    assert "private query" not in caplog.text


@pytest.mark.asyncio
async def test_cohere_timeout_is_explicit_and_preserves_candidates(monkeypatch):
    def slow(request):
        raise httpx.ReadTimeout("private body", request=request)
    calls = install_transport(monkeypatch, slow)
    hits = [_passage("LAW", "L", "Law", "Evidence")]
    result = await rerank("query", hits)
    assert len(calls) == 1
    assert result.status == "FAILED"
    assert result.passages == hits


def test_budget_preserves_whole_exceptions_and_flags_omitted_dependency(monkeypatch):
    rule = _passage("INTERNAL_RULE", "NQ", "Rule", "Khiển trách.")
    law = _passage("LAW", "L", "Law", "Khiển trách.")
    exception = replace(_passage("LAW", "L", "Law", "Trừ trường hợp " + "x" * 5000), origin="graph")
    monkeypatch.setattr(settings, "RETRIEVAL_EVIDENCE_MAX_BYTES", evidence_size(rule) + evidence_size(law))
    result = select_evidence([rule, law, exception])
    assert {item.content for item in result.passages} == {"Khiển trách."}
    assert len(result.passages) == 2
    assert "EVIDENCE_BUDGET_EXCEEDED" in result.gaps
    assert result.size_unit == "utf8_bytes"
    assert all(item.retrieval_status == "INCOMPLETE" for item in result.passages)


def test_exact_token_budget_uses_supplied_tokenizer(tmp_path, monkeypatch):
    tokenizer = Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = Whitespace()
    path = tmp_path / "tokenizer.json"
    tokenizer.save(str(path))
    monkeypatch.setattr(settings, "SYNTHESIS_TOKENIZER_PATH", str(path))
    hit = _passage("LAW", "L", "Law", "Evidence")
    from src.features.cite.model.rerank import document_text
    assert evidence_size(hit) == len(tokenizer.encode(document_text(hit)).ids)
    assert select_evidence([hit]).size_unit == "tokens"


def test_administrative_penalty_cannot_fill_employee_sanction_authority():
    rule = _passage("INTERNAL_RULE", "NQ", "Rule", "Khiển trách.")
    penalty = _passage("DECREE", "283/2026", "Nghị định xử phạt hành chính", "Phạt tiền.")
    result = select_evidence([penalty, rule])
    assert [item.chunk_id for item in result.passages] == [rule.chunk_id]
    assert "MISSING_AUTHORITY" in result.gaps


@pytest.mark.asyncio
async def test_degraded_rerank_keeps_synthesis_and_a_proposal_for_review(monkeypatch):
    law = _passage("LAW", "L", "Law", "Khiển trách.")
    rule = _passage("INTERNAL_RULE", "NQ", "Rule", "Khiển trách.")
    selected = select_evidence([law, rule], status="MISSING_KEY")
    handoff = handoff_node({"hits": selected.passages, "facts": _READY,
                           "incident_date": date(2026, 3, 1), "agent_run_id": uuid4()})["handoff"]
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test")
    complete = AsyncMock(return_value=_supported("WARNING", law, rule))
    monkeypatch.setattr("src.features.answer.model.synthesis._complete", complete)
    from src.features.answer.model.layers import split_passages
    result = await synthesize(handoff, split_passages(selected.passages))
    complete.assert_awaited_once()
    assert result.operational_status == "OK"
    assert not result.downstream_handoff.can_recommend
    assert result.sanction_assessment.recommended_sanction == "WARNING"
    assert result.risk_assessment.level == "HIGH"


def test_unrelated_law_cannot_unlock_a_company_level_even_with_claimed_conditions():
    law = _passage("LAW", "L", "Law", "Hợp đồng của người nước ngoài không vượt quá giấy phép lao động.")
    rule = _passage("INTERNAL_RULE", "NQ", "Rule", "Tiết lộ mã nguồn thì sa thải.")
    result = _supported("DISMISSAL", law, rule)
    assert not result.downstream_handoff.can_recommend


def test_invented_confirmed_fact_forces_unknown():
    law = _passage("LAW", "L", "Law", _ART_124)
    rule = _passage("INTERNAL_RULE", "NQ", "Rule", "Khiển trách.")
    accepted = _supported("WARNING", law, rule)
    assert accepted.downstream_handoff.can_recommend
    altered = accepted.applicable_rules[0].conditions[0].model_copy(update={"fact_value": "999 ngày"})
    raw = accepted.model_copy(update={"applicable_rules": [
        accepted.applicable_rules[0].model_copy(update={"conditions": [altered]}), accepted.applicable_rules[1]]})
    result = guard(raw, [law, rule], facts=_READY)
    assert result.sanction_assessment.status == "NEED_LEGAL_REVIEW"
    assert "absence_days" not in result.case_summary.missing_facts
    assert result.sanction_assessment.recommended_sanction == "WARNING"
    assert not result.downstream_handoff.can_recommend
    assert result.risk_assessment.level == "HIGH"


@pytest.mark.asyncio
async def test_coverage_retry_is_bounded_and_runs_after_semantic_seed_ranking():
    law = _passage("LAW", "L", "Law", "Hình thức khiển trách.")
    rule = _passage("INTERNAL_RULE", "NQ", "Rule", "Tiết lộ mã nguồn bị khiển trách.")
    calls = []
    async def arm(state):
        return {"similarity": [law]}
    async def empty(state):
        return {}
    async def ranker(query, hits):
        calls.append("rank")
        return RerankResult([replace(item, rerank_score=0.9) for item in hits], "OK")
    async def expand(state):
        assert calls == ["rank"]
        assert state["seeds"][0].chunk_id == law.chunk_id
        calls.append("expand")
        return {"expanded": state["fused"]}
    async def supplement(state):
        calls.append("supplement")
        return {"expanded": [law, rule], "supplemented": True}
    state = await pipeline.compile_retrieval(arm, empty, empty, expand=expand,
                                            supplement=supplement, reranker=ranker).ainvoke({"query": disclosure_query()})
    assert calls.count("supplement") == 1
    assert not state["evidence_gaps"]
    assert all(item.retrieval_status == "OK" for item in state["hits"])
    assert {item.chunk_id for item in state["hits"]} == {law.chunk_id, rule.chunk_id}


@pytest.mark.asyncio
async def test_real_bm25_uses_full_eligible_corpus_and_preserves_headings(graph_db):  # noqa: F811
    # Execute the new BM25 SQL on the relational fixture; only scoring is Python.
    first, second = graph_db.chunk(), graph_db.chunk()
    from sqlalchemy import text
    await graph_db.execute(text("UPDATE document_chunks SET content='hợp đồng thời hạn' WHERE id=:id").bindparams(id=first.hex))
    await graph_db.execute(text("UPDATE document_chunks SET content='tiết lộ mã nguồn', section_title='Bảo mật' WHERE id=:id").bindparams(id=second.hex))
    found = await fetch_by_bm25(graph_db, date(2026, 3, 1), ["mã nguồn", "tiết lộ"], 1)
    assert [item.chunk_id for item in found] == [second]
    assert found[0].content == "tiết lộ mã nguồn"
    assert found[0].section_title == "Bảo mật"


@pytest.mark.asyncio
async def test_actual_deepseek_request_uses_documented_max_tokens(monkeypatch):
    from src.features.answer.model import synthesis
    from src.services import chat_client
    original = chat_client.ChatOpenAI
    captured = {}
    def respond(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "test", "object": "chat.completion", "created": 0, "model": "deepseek-flash",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps({
                "case_summary": {"facts": {}}, "sanction_assessment": {"status": "NOT_SUPPORTED", "reason": "Thiếu căn cứ"},
                "risk_assessment": {"level": "HIGH"}})}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(chat_client, "ChatOpenAI", lambda **kwargs: original(http_async_client=client, **kwargs))
        monkeypatch.setattr(settings, "LLM_PROVIDER", "deepseek")
        monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test")
        result = await synthesis._complete([{"role": "user", "content": "test"}], 0, "deepseek-flash")
    assert result.sanction_assessment.recommended_sanction is None
    assert captured["max_tokens"] == settings.SYNTHESIS_MAX_TOKENS
    assert "max_completion_tokens" not in captured
    assert captured["reasoning_effort"] == "low"
    assert captured["thinking"]["type"] == "enabled"


def test_retrieval_metrics_accept_complete_alternative_bundle():
    from eval.retrieval.evaluate import CaseReference, measures
    first, second, third = uuid4(), uuid4(), uuid4()
    reference = CaseReference(case_id="fixture", reference_status="expert_reviewed", incident_date=date(2026, 1, 1),
                              description="fixture", evidence_bundles=[[first, second], [first, third]])
    scored = measures(reference, {"candidate_ids": [str(first), str(third)], "selected_ids": [str(first), str(third)],
                                 "rerank_status": "OK"})
    assert scored["complete_bundle"] is True
    assert scored["candidate_recall"] == scored["final_recall"] == 1


@pytest.mark.asyncio
async def test_readiness_detects_missing_cohere_key(monkeypatch):
    from unittest.mock import AsyncMock

    from src.features.health.model import readiness
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "test")
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test")
    session = AsyncMock()
    session.scalar.return_value = 1
    ready, checks = await readiness(session)
    assert checks["rerank_configured"] is False
    assert ready is False


@pytest.mark.asyncio
async def test_production_graph_records_arm_status_and_preserves_source_coverage(graph_db, monkeypatch):  # noqa: F811
    from sqlalchemy import text
    law_id, rule_id = graph_db.chunk(), graph_db.chunk()
    await graph_db.execute(text("UPDATE document_chunks SET content='Hình thức sa thải áp dụng khi tiết lộ mã nguồn' WHERE id=:id").bindparams(id=law_id.hex))
    await graph_db.execute(text("UPDATE document_chunks SET content='Tiết lộ mã nguồn cho đối thủ thì sa thải' WHERE id=:id").bindparams(id=rule_id.hex))
    await graph_db.execute(text("UPDATE policies SET policy_type='INTERNAL_RULE' WHERE id=(SELECT pv.policy_id FROM policy_versions pv JOIN documents d ON d.policy_version_id=pv.id JOIN document_chunks c ON c.document_id=d.id WHERE c.id=:id)").bindparams(id=rule_id.hex))
    async def no_embedding(*args):
        return []
    async def ranker(query, hits):
        return RerankResult([replace(item, rerank_score=0.9) for item in hits], "OK")
    monkeypatch.setattr(pipeline, "similarity_passages", no_embedding)
    monkeypatch.setattr(pipeline, "rerank", ranker)
    state = await pipeline.build_retrieval_graph(graph_db).ainvoke({"query": disclosure_query(), "terms": []})
    assert state["arm_status"] == {"similarity": "OK", "bm25": "OK", "lexical": "OK"}
    assert {item.chunk_id for item in state["hits"]} == {law_id, rule_id}
    assert state["evidence_gaps"] == []
    assert state["rerank_status"] == "OK"


@pytest.mark.asyncio
async def test_graph_failure_prevents_successful_evidence_quality():
    law = _passage("LAW", "L", "Law", "Khiển trách.")
    rule = _passage("INTERNAL_RULE", "NQ", "Rule", "Khiển trách.")
    async def arm(state):
        return {"similarity": [law, rule]}
    async def empty(state):
        return {}
    async def ranker(query, hits):
        return RerankResult([replace(item, rerank_score=0.9) for item in hits], "OK")
    async def failed_graph(state):
        return {"expanded": state["fused"], "graph_status": "FAILED"}
    state = await pipeline.compile_retrieval(arm, empty, empty, expand=failed_graph, reranker=ranker).ainvoke({"query": disclosure_query()})
    assert state["rerank_status"] == "FAILED"
    assert all(item.retrieval_status == "DEGRADED" for item in state["hits"])
    assert state["trace"]["rerank_errors"]["graph"] == "GRAPH_EXPANSION_FAILED"


@pytest.mark.parametrize('problem', ['unsatisfied', 'missing_fact', 'gap', 'conflict'])
def test_supported_flag_cannot_override_missing_or_conflicting_conditions(problem):
    from src.features.answer.model.assessment import Conflict, EvidenceGap
    law = _passage('LAW', 'L', 'Law', _ART_124)
    rule = _passage('INTERNAL_RULE', 'NQ', 'Rule', 'Khiển trách.')
    raw = _supported('WARNING', law, rule)
    assert raw.downstream_handoff.can_recommend
    if problem == 'unsatisfied':
        condition = raw.applicable_rules[0].conditions[0].model_copy(update={'result': 'NOT_SATISFIED'})
        raw = raw.model_copy(update={'applicable_rules': [raw.applicable_rules[0].model_copy(update={'conditions': [condition]}), raw.applicable_rules[1]]})
    elif problem == 'missing_fact':
        raw = raw.model_copy(update={'case_summary': raw.case_summary.model_copy(update={'missing_facts': ['notice_form']})})
    elif problem == 'gap':
        raw = raw.model_copy(update={'evidence_gaps': [EvidenceGap(fact='reason', reason='Thiếu tình tiết', question_for_user='Lý do là gì?')]})
    else:
        raw = raw.model_copy(update={'conflicts': [Conflict(topic='mức xử lý', description='Hai nguồn mâu thuẫn')]})
    checked = guard(raw, [law, rule], facts=_READY)
    assert not checked.downstream_handoff.can_recommend
    if problem in {"unsatisfied", "conflict"}:
        assert checked.sanction_assessment.recommended_sanction is None
    else:
        assert checked.sanction_assessment.recommended_sanction == "WARNING"
        assert checked.risk_assessment.level == "HIGH"


@pytest.mark.asyncio
async def test_timeout_model_is_not_retried_as_schema_repair(monkeypatch):
    from src.features.answer.model import synthesis
    from src.features.answer.model.layers import split_passages
    law = _passage('LAW', 'L', 'Law', _ART_124)
    rule = _passage('INTERNAL_RULE', 'NQ', 'Rule', 'Khiển trách.')
    handoff = handoff_node({'hits': [law, rule], 'facts': _READY, 'incident_date': date(2026, 3, 1),
                           'agent_run_id': uuid4()})['handoff']
    monkeypatch.setattr(settings, 'DEEPSEEK_API_KEY', 'test')
    monkeypatch.setattr(settings, 'MODEL_NAME', 'primary')
    monkeypatch.setattr(settings, 'FALLBACK_MODEL_NAME', 'fallback')
    calls = []
    async def slow(messages, attempt, model_name):
        calls.append((model_name, attempt))
        raise TimeoutError()
    monkeypatch.setattr(synthesis, '_complete', slow)
    result = await synthesize(handoff, split_passages([law, rule]))
    assert calls == [('primary', 0), ('fallback', 0)]
    assert result.operational_status == 'LLM_FAILED'
    assert not result.downstream_handoff.can_recommend


@pytest.mark.asyncio
@pytest.mark.parametrize('table', ['policies', 'documents'])
async def test_soft_deleted_sources_are_excluded_from_bm25(graph_db, table):  # noqa: F811
    from sqlalchemy import text
    graph_db.chunk()
    # Table is drawn only from this fixed test parameter, never application input.
    await graph_db.execute(text(f"UPDATE {table} SET deleted_at='2026-01-01'"))
    assert await fetch_by_bm25(graph_db, date(2026, 3, 1), ['Evidence'], 10) == []
