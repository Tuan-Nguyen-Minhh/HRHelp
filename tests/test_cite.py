from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from src.features.cite.model.bm25 import bm25_rank
from src.features.cite.model.graph import handoff_node
from src.features.cite.model.page_index import select_article_heads
from src.features.cite.model.pipeline import compile_retrieval
from src.features.cite.model.query import SearchQuery
from src.features.cite.model.rank import rank_passages
from src.features.cite.model.rrf import reciprocal_rank_fusion
from src.features.cite.model.similarity import similarity_passages
from src.features.cite.model.store import ChunkHit, article_index_stmt, bm25_stmt, in_force_filter
from src.features.cite.model.terms import search_terms
from src.features.clarify.model.catalog import ABSENCE
from src.features.clarify.model.turns import _cited_text
from src.models.policy_versions import PolicyVersion
from tests.test_answer import _passage


def test_search_terms_lead_with_the_absence_hint_and_drop_stopwords():
    terms = search_terms(ABSENCE, ["Số ngày nghỉ không phép: 5"], "của nhân viên")
    assert "thải" in terms
    assert "phép" in terms
    assert "ngày" not in terms
    assert "của" not in terms


def test_rank_keeps_the_closer_chunk_and_drops_a_miss():
    hit = _passage("LAW", "BLLD", "Luật", "Sa thải người lao động nghỉ không phép.")
    miss = _passage("LAW", "KHAC", "Khác", "Nghỉ hàng năm được hưởng nguyên lương.")
    ranked = rank_passages([miss, hit], ["thải", "phép"], limit=8)
    assert [item.policy_code for item in ranked] == ["BLLD"]
    assert ranked[0].score > 0


def test_bm25_prefers_the_chunk_that_uses_more_query_terms():
    close = _passage("LAW", "BLLD", "Luật", "Sa thải người lao động nghỉ không phép.")
    far = _passage("LAW", "KHAC", "Khác", "Nghỉ hàng năm được hưởng nguyên lương.")
    ranked = bm25_rank([far, close], ["thải", "phép"], limit=2)
    assert [item.policy_code for item in ranked] == ["BLLD"]


def test_rrf_promotes_a_chunk_that_appears_in_more_than_one_list():
    law = _passage("LAW", "BLLD", "Luật", "Sa thải.")
    penalty = _passage("DECREE", "283", "Nghị định", "Phạt tiền.")
    fused = reciprocal_rank_fusion([[law], [penalty, law], [law]], limit=2)
    assert [item.policy_code for item in fused] == ["BLLD", "283"]


@pytest.mark.asyncio
async def test_retrieval_graph_fuses_similarity_bm25_and_lexical_then_reranks():
    law = _passage("LAW", "BLLD", "Luật", "Sa thải người lao động.")
    penalty = _passage("DECREE", "283", "Nghị định", "Phạt tiền.")

    async def similarity(_state):
        return {"similarity": [law]}

    async def bm25(_state):
        return {"bm25": [penalty]}

    async def lexical(_state):
        return {"lexical": [law, penalty]}

    async def page_index(_state):
        raise AssertionError("page index runs only when hybrid hits are empty")

    graph = compile_retrieval(similarity, bm25, lexical, page_index)
    state = await graph.ainvoke({"query": _query(), "terms": ["thải"]})
    assert [item.policy_code for item in state["hits"]] == ["BLLD", "283"]
    assert state["hits"][0].score > state["hits"][1].score
    assert state["retrieval"] == "hybrid"


def _chunk(
    version,
    policy_type: str,
    code: str,
    article: str,
    chunk_index: int,
    content: str,
    section_title: str | None = None,
    article_title: str | None = None,
) -> ChunkHit:
    return ChunkHit(
        chunk_id=uuid4(),
        policy_version_id=version,
        content=content,
        article=article,
        clause=None,
        point=None,
        policy_type=policy_type,
        policy_code=code,
        policy_name=code,
        section_title=section_title,
        chunk_index=chunk_index,
        article_title=article_title,
    )


def _graph_state(hits: list) -> dict:
    return {
        "incident_date": date(2026, 3, 1),
        "family": ABSENCE,
        "facts": {},
        "agent_run_id": uuid4(),
        "hits": hits,
    }


def _arm(name: str):
    async def node(_state):
        return {name: []}

    return node


def _query() -> SearchQuery:
    return SearchQuery(
        text="nghỉ không phép",
        incident_date=date(2026, 3, 1),
        agent_run_id=uuid4(),
        family=ABSENCE,
        fact_lines=[],
        description="nghỉ không phép",
    )


def test_page_index_keeps_one_head_per_article_and_drops_a_non_anchor():
    version = uuid4()
    early = _chunk(version, "LAW", "BLLD", "125", 1, "Sa thải người lao động nghỉ không phép.")
    later = _chunk(version, "LAW", "BLLD", "125", 4, "Sa thải ở khoản sau của cùng điều.")
    titled = _chunk(version, "LAW", "BLLD", "36", 2, "Nghỉ hàng năm được hưởng lương.", article_title="Quyền đơn phương chấm dứt")
    miss = _chunk(version, "LAW", "BLLD", "10", 0, "Nghỉ hàng năm được hưởng nguyên lương.")
    decree = _chunk(uuid4(), "DECREE", "283", "1", 0, "Phạt tiền khi sa thải trái quy định.")
    rule = _chunk(uuid4(), "INTERNAL_RULE", "NQ", "4", 3, "Giờ làm việc.", section_title="Nội quy sa thải")
    heads = select_article_heads(
        [later, miss, decree, early, rule, titled],
        ["sa thải", "đơn phương chấm dứt"],
        limit=8,
    )
    assert [(item.policy_code, item.article) for item in heads] == [
        ("BLLD", "36"),
        ("BLLD", "125"),
        ("283", "1"),
        ("NQ", "4"),
    ]
    assert heads[1].chunk_id == early.chunk_id
    assert heads[0].origin == "page_index"
    assert heads[0].score == 0.0


@pytest.mark.asyncio
async def test_empty_hybrid_walks_the_page_index_once():
    head = replace(_passage("LAW", "BLLD", "Luật", "Sa thải."), origin="page_index", score=0.0)
    calls = {"n": 0}

    async def page_index(_state):
        calls["n"] += 1
        return {"hits": [head], "retrieval": "page_index"}

    graph = compile_retrieval(_arm("similarity"), _arm("bm25"), _arm("lexical"), page_index)
    state = await graph.ainvoke({"query": _query(), "terms": ["thải"]})
    assert calls["n"] == 1
    assert [item.policy_code for item in state["hits"]] == ["BLLD"]
    assert state["retrieval"] == "page_index"


@pytest.mark.asyncio
async def test_empty_page_index_leaves_the_handoff_without_passages():
    async def page_index(_state):
        return {"hits": [], "retrieval": "empty"}

    graph = compile_retrieval(_arm("similarity"), _arm("bm25"), _arm("lexical"), page_index)
    state = await graph.ainvoke({"query": _query(), "terms": ["thải"]})
    assert state["hits"] == []
    assert state["retrieval"] == "empty"


def test_handoff_records_page_index_and_abstain():
    head = replace(_passage("LAW", "BLLD", "Luật", "Sa thải."), origin="page_index", score=0.0)
    found = handoff_node(_graph_state([head]))["handoff"]
    assert found.retrieval == "page_index"
    assert found.passages[0].origin == "page_index"
    missed = handoff_node(_graph_state([]))["handoff"]
    assert missed.retrieval == "empty"
    assert missed.passages == []
    assert "Chưa lập căn cứ" in _cited_text(missed)
    assert "mục lục" in _cited_text(found)
    hybrid = found.model_copy(update={"retrieval": "hybrid"})
    assert "Đã đối chiếu 1 đoạn" in _cited_text(hybrid)


def test_article_index_stmt_reads_the_outline_inside_the_in_force_window():
    stmt = article_index_stmt(date(2026, 3, 1), ["đơn phương chấm dứt"], 80)
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "section_title" in sql
    assert "article_title" in sql
    assert "chunk_index" in sql
    assert "effective_from" in sql
    assert "ACTIVE" in sql
    assert "đơn phương chấm dứt" in sql


def test_bm25_stmt_ranks_search_tsv_inside_the_in_force_window():
    stmt = bm25_stmt(date(2026, 3, 1), 8)
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "search_tsv" in sql
    assert "ts_rank" in sql
    assert "@@" in sql
    assert "effective_from" in sql
    assert "policy_versions.status" in sql
    assert "ingest_status" in sql


@pytest.mark.asyncio
async def test_similarity_without_a_vector_stays_empty_when_the_key_is_missing(monkeypatch):
    monkeypatch.setattr("src.features.cite.model.similarity._client", None)
    monkeypatch.setattr("src.core.config.settings.MISTRAL_API_KEY", "")
    assert await similarity_passages(None, _query(), 8) == []


@pytest.mark.asyncio
async def test_similarity_skips_a_1536_vector_without_embedding_again():
    query = SearchQuery(
        text="nghỉ không phép",
        incident_date=date(2026, 3, 1),
        agent_run_id=uuid4(),
        family=ABSENCE,
        fact_lines=[],
        description="nghỉ không phép",
        embedding=tuple(0.0 for _ in range(1536)),
    )
    assert await similarity_passages(None, query, 8) == []


def test_in_force_filter_requires_the_incident_date_on_both_bounds():
    stmt = select(PolicyVersion.id).where(in_force_filter(date(2026, 3, 1)))
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "effective_from" in sql
    assert "effective_to" in sql
    assert "ACTIVE" in sql
    assert "2026-03-01" in sql
