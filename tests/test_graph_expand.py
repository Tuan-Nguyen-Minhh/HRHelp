"""Graph expansion contracts, executable SQL filtering, and pipeline/audit wiring."""

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql

from src.features.cite.model import graph_expand, pipeline, search
from src.features.cite.model.graph import handoff_node
from src.features.cite.model.graph_expand import (
    GRAPH_EDGE_DECAY,
    GRAPH_MAX_EXPANSION,
    expand_node,
    expand_passages,
)
from src.features.cite.model.page_index import retrieval_mode
from src.features.cite.model.passage import Passage
from src.features.cite.model.query import SearchQuery
from src.features.cite.model.store import fetch_graph_neighbors, graph_edge_stmt


def passage(score=1.0):
    return Passage(uuid4(), uuid4(), "Evidence", "125", None, None, score, "LAW", "BLLD", "Labour Code")


def query():
    return SearchQuery("absence", date(2026, 3, 1), uuid4(), "GENERAL", [], "absence")


def test_merge_deduplicates_preserves_fused_and_decays_neighbors():
    first, second, neighbor = passage(1), passage(0.6), passage(100)
    fused = [first, second]
    result = expand_passages(fused, [replace(first, score=100), neighbor, neighbor])
    assert [item.chunk_id for item in result] == [first.chunk_id, second.chunk_id, neighbor.chunk_id]
    assert result[:2] == fused  # fused wins the tie, with original scores/provenance
    assert result[2].score == first.score * GRAPH_EDGE_DECAY
    assert result[2].origin == "graph"
    assert fused == [first, second]
    assert neighbor.score == 100


def test_merge_caps_only_new_distinct_neighbors_and_sorts_by_score():
    fused = [passage(1), passage(0.1)]
    neighbors = [passage() for _ in range(20)]
    result = expand_passages(fused, [fused[0], neighbors[0], neighbors[0], *neighbors[1:]])
    assert len(result) == len(fused) + GRAPH_MAX_EXPANSION
    assert result[-1] == fused[1]
    assert [item.chunk_id for item in result[1:-1]] == [item.chunk_id for item in neighbors[:12]]
    assert expand_passages([], neighbors) == []


@pytest.fixture
def graph_db():
    """Execute production SQL on minimal relational tables, without a live corpus/API."""
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        for ddl in (
            "CREATE TABLE policies (id CHAR(32) PRIMARY KEY, code TEXT, name TEXT, policy_type TEXT, is_active BOOL, deleted_at DATETIME)",
            "CREATE TABLE policy_versions (id CHAR(32) PRIMARY KEY, policy_id CHAR(32), status TEXT, effective_from DATE, effective_to DATE)",
            "CREATE TABLE documents (id CHAR(32) PRIMARY KEY, policy_version_id CHAR(32), ingest_status TEXT, deleted_at DATETIME)",
            "CREATE TABLE document_chunks (id CHAR(32) PRIMARY KEY, document_id CHAR(32), content TEXT, article TEXT, clause TEXT, point TEXT, section_title TEXT, metadata JSON)",
            "CREATE TABLE chunk_references (ref_id INTEGER PRIMARY KEY, source_chunk_id CHAR(32), target_chunk_id CHAR(32), rule TEXT, confidence TEXT, needs_review BOOL)",
        ):
            connection.execute(text(ddl))

        class Session:
            async def execute(self, statement):
                return connection.execute(statement)

            @asynccontextmanager
            async def begin_nested(self):
                with connection.begin_nested():
                    yield

            def chunk(self, *, start="2020-01-01", end=None, status="ACTIVE", active=True, ingest="EMBEDDED"):
                policy_id, version_id, document_id, chunk_id = [uuid4() for _ in range(4)]
                connection.execute(
                    text("INSERT INTO policies (id, code, name, policy_type, is_active) VALUES (:id, 'LAW', 'Law', 'LAW', :active)"),
                    {"id": policy_id.hex, "active": active},
                )
                connection.execute(
                    text("INSERT INTO policy_versions VALUES (:id, :policy, :status, :start, :end)"),
                    {"id": version_id.hex, "policy": policy_id.hex, "status": status, "start": start, "end": end},
                )
                connection.execute(
                    text("INSERT INTO documents (id, policy_version_id, ingest_status) VALUES (:id, :version, :ingest)"),
                    {"id": document_id.hex, "version": version_id.hex, "ingest": ingest},
                )
                connection.execute(
                    text("INSERT INTO document_chunks (id, document_id, content, article, clause, point) VALUES (:id, :doc, 'Evidence', '125', NULL, NULL)"),
                    {"id": chunk_id.hex, "doc": document_id.hex},
                )
                return chunk_id

            def edge(self, source, target, *, confidence="HIGH", review=False, rule="EXPLICIT"):
                connection.execute(
                    text(
                        "INSERT INTO chunk_references (source_chunk_id, target_chunk_id, rule, confidence, needs_review) VALUES (:source, :target, :rule, :confidence, :review)"
                    ),
                    {
                        "source": source.hex,
                        "target": target.hex if target else None,
                        "rule": rule,
                        "confidence": confidence,
                        "review": review,
                    },
                )

        yield Session()
    engine.dispose()


@pytest.mark.asyncio
async def test_store_traverses_both_directions_once_and_preserves_edge_provenance(graph_db):
    seed, outgoing, incoming, hop2 = [graph_db.chunk() for _ in range(4)]
    graph_db.edge(seed, outgoing)
    graph_db.edge(seed, outgoing, rule="DEFAULT_SELF")
    graph_db.edge(incoming, seed)
    graph_db.edge(outgoing, hop2)
    graph_db.edge(seed, seed)
    graph_db.edge(seed, None)
    result = await fetch_graph_neighbors(graph_db, date(2026, 3, 1), [seed], 12)
    assert {item.chunk_id for item in result} == {outgoing, incoming}
    assert all(item.origin == "graph" for item in result)
    by_id = {item.chunk_id: item for item in result}
    assert len(by_id[outgoing].graph_edges) == 2
    edge = by_id[incoming].graph_edges[0]
    assert (edge.seed_chunk_id, edge.source_chunk_id, edge.target_chunk_id) == (seed, incoming, seed)
    assert await fetch_graph_neighbors(graph_db, date(2026, 3, 1), [], 12) == []
    assert await fetch_graph_neighbors(graph_db, date(2026, 3, 1), [seed], 0) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("incoming", [False, True])
@pytest.mark.parametrize(
    "kind", ["low", "review", "expired", "future", "inactive_version", "inactive_policy", "unreadable"]
)
async def test_store_filters_edges_and_neighbor_eligibility_before_limit(graph_db, incoming, kind):
    seed, valid = graph_db.chunk(), graph_db.chunk()
    options = {
        "expired": {"end": "2026-02-28"},
        "future": {"start": "2026-03-02"},
        "inactive_version": {"status": "DRAFT"},
        "inactive_policy": {"active": False},
        "unreadable": {"ingest": "FAILED"},
    }
    invalid = graph_db.chunk(**options.get(kind, {}))
    for neighbor in (invalid, valid):
        source, target = (neighbor, seed) if incoming else (seed, neighbor)
        graph_db.edge(
            source,
            target,
            confidence="LOW" if neighbor == invalid and kind == "low" else "HIGH",
            review=neighbor == invalid and kind == "review",
        )
    result = await fetch_graph_neighbors(graph_db, date(2026, 3, 1), [seed], 1)
    assert [item.chunk_id for item in result] == [valid]


@pytest.mark.asyncio
async def test_store_deduplicates_shared_neighbors_and_excludes_existing_hits_before_cap(graph_db):
    first, second, existing = [graph_db.chunk() for _ in range(3)]
    boundary = graph_db.chunk(start="2026-03-01", end="2026-03-01")
    graph_db.edge(first, existing)
    graph_db.edge(first, boundary)
    graph_db.edge(second, boundary)
    result = await fetch_graph_neighbors(graph_db, date(2026, 3, 1), [first, second], 1, exclude_chunk_ids=[existing])
    assert [item.chunk_id for item in result] == [boundary]
    assert {edge.seed_chunk_id for edge in result[0].graph_edges} == {first, second}


def test_edge_sql_uses_indexed_direction_columns():
    seed = uuid4()
    for incoming, column in ((False, "source_chunk_id"), (True, "target_chunk_id")):
        sql = str(
            graph_edge_stmt([seed], incoming=incoming).compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        assert f"chunk_references.{column} IN" in sql
        assert "confidence = 'HIGH'" in sql
        assert "needs_review IS false" in sql
        assert "target_chunk_id IS NOT NULL" in sql


@pytest.mark.asyncio
async def test_node_selects_top_five_and_recovers_transaction_after_sql_error(graph_db, monkeypatch):
    fused = [passage() for _ in range(8)]
    fetch = AsyncMock(return_value=[passage()])
    monkeypatch.setattr(graph_expand, "fetch_graph_neighbors", fetch)
    result = await expand_node(graph_db)({"query": query(), "fused": fused})
    assert len(result["expanded"]) == 9
    assert fetch.call_args.args[2] == [item.chunk_id for item in fused[:5]]
    assert fetch.call_args.kwargs["exclude_chunk_ids"] == [item.chunk_id for item in fused]

    async def broken(session, *_args, **_kwargs):
        await session.execute(text("SELECT * FROM missing_graph_table"))

    monkeypatch.setattr(graph_expand, "fetch_graph_neighbors", broken)
    assert await expand_node(graph_db)({"query": query(), "fused": fused}) == {"expanded": fused, "graph_status": "FAILED"}
    assert (await graph_db.execute(text("SELECT 1"))).scalar_one() == 1
    fetch.reset_mock()
    monkeypatch.setattr(graph_expand, "fetch_graph_neighbors", fetch)
    assert await expand_node(graph_db)({"query": query(), "fused": []}) == {"expanded": []}
    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_pipeline_orders_expansion_before_rerank_and_preserves_fused(monkeypatch):
    original, neighbor = passage(), passage()
    calls = []

    def arm(name, hits):
        async def node(_state):
            calls.append(name)
            return {name: hits}

        return node

    async def expand(state):
        assert set(calls) == {"similarity", "bm25", "lexical", "seed_rerank"}
        assert state["fused"][0].chunk_id == original.chunk_id
        calls.append("expand")
        return {"expanded": expand_passages(state["fused"], [neighbor])}

    async def rerank(_query, hits):
        from src.features.cite.model.rerank import RerankResult
        if len(hits) == 1:
            calls.append("seed_rerank")
        else:
            assert "expand" in calls
            calls.append("rerank")
            assert len(hits) == 2
        return RerankResult(hits, "OK")

    monkeypatch.setattr(pipeline, "rerank", rerank)
    graph = pipeline.compile_retrieval(
        arm("similarity", [original]), arm("bm25", []), arm("lexical", []), expand=expand
    )
    state = await graph.ainvoke({"query": query(), "terms": []})
    assert calls.index("seed_rerank") < calls.index("expand") < calls.index("rerank")
    assert len(state["fused"]) == 1
    assert [item.chunk_id for item in state["hits"]] == [item.chunk_id for item in state["expanded"]]
    assert state["retrieval"] == "hybrid"


@pytest.mark.asyncio
async def test_pipeline_without_expansion_is_compatible():
    original = passage()

    async def similarity(_state):
        return {"similarity": [original]}

    async def bm25(_state):
        return {"bm25": []}

    async def lexical(_state):
        return {"lexical": []}

    state = await pipeline.compile_retrieval(similarity, bm25, lexical).ainvoke({"query": query(), "terms": []})
    assert [item.chunk_id for item in state["hits"]] == [item.chunk_id for item in state["fused"]]
    assert state["rerank_status"] == "MISSING_KEY"
    assert state["hits"][0].retrieval_status == "DEGRADED"


@pytest.mark.asyncio
async def test_search_audits_graph_hits_and_handoff_keeps_origin(graph_db, monkeypatch):
    seed, neighbor = graph_db.chunk(), graph_db.chunk()
    graph_db.edge(seed, neighbor)
    fused = [replace(passage(), chunk_id=seed)]
    hits = expand_passages(fused, await fetch_graph_neighbors(graph_db, query().incident_date, [seed], 12))

    class Graph:
        async def ainvoke(self, _state):
            return {"hits": hits}

    monkeypatch.setattr(search, "build_retrieval_graph", lambda _session: Graph())
    for name in ("begin_search", "complete_search", "save_retrievals"):
        monkeypatch.setattr(search, name, AsyncMock())
    result = await search.search_policies(graph_db, query())
    ledger_hits = search.save_retrievals.call_args.args[2]
    assert ledger_hits[1].retrieval_method == "graph"
    output = search.complete_search.call_args.args[2]
    assert output["graph_provenance"][0]["edges"][0]["source_chunk_id"] == str(seed)
    assert output["retrieval"] == retrieval_mode(result) == "hybrid"
    message = handoff_node({"hits": hits, "incident_date": query().incident_date, "agent_run_id": uuid4()})["handoff"]
    assert message.passages[1].origin == "graph"
