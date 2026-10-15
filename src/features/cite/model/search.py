"""Run the retrieval graph and audit it on the agent ledger.

The graph runs three search arms, then RRF, hop-1 graph expansion, and rerank.
An empty rerank walks the article outline before the handoff is packed.
"""

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.runs import RetrievalHit, begin_search, complete_search, save_retrievals
from src.features.cite.model.page_index import retrieval_mode
from src.features.cite.model.passage import Passage
from src.features.cite.model.pipeline import build_retrieval_graph
from src.features.cite.model.query import SearchQuery, act_text, facet_queries
from src.features.cite.model.terms import search_terms

logger = logging.getLogger(__name__)


async def search_policies(session: AsyncSession, query: SearchQuery) -> list[Passage]:
    """Run the retrieval sub-agent and return the passages the handoff may carry."""
    started = time.perf_counter()
    terms = search_terms(query.family, query.fact_lines, query.description)
    logger.info(
        "agent_stage start stage=retrieval run_id=%s family=%s incident_date=%s query_chars=%s terms=%s",
        query.agent_run_id,
        query.family,
        query.incident_date,
        len(query.text or ""),
        len(terms),
    )
    tool = await begin_search(
        session,
        query.agent_run_id,
        {
            "query": query.text,
            "incident_date": query.incident_date.isoformat(),
            "terms": terms,
            "retrievers": ["similarity", "okapi_bm25", "phrase_lexical", "page_index"],
            "expansion": "graph_hop1",
            "act_query": act_text(query),
            "facet_queries": facet_queries(query),
        },
    )
    graph = build_retrieval_graph(session)
    state = await graph.ainvoke({"query": query, "terms": terms})
    ranked = list(state.get("hits") or [])
    output = _output(ranked)
    output.update({key: state.get(key) for key in
                   ("rerank_status", "graph_status", "arm_status", "evidence_gaps", "evidence_size", "evidence_size_unit", "supplemented", "trace")})
    output["candidate_rankings"] = {
        name: [{"chunk_id": str(item.chunk_id), "score": item.score} for item in state.get(name, [])]
        for name in ("similarity", "bm25", "lexical", "fused")
    }
    await complete_search(session, tool, output)
    await save_retrievals(
        session,
        query.agent_run_id,
        [RetrievalHit(passage.chunk_id, passage.score, passage.origin or "hybrid") for passage in ranked],
    )
    logger.info(
        "agent_stage end stage=retrieval run_id=%s latency_ms=%s hits=%s mode=%s graph_hits=%s",
        query.agent_run_id,
        int((time.perf_counter() - started) * 1000),
        len(ranked),
        retrieval_mode(ranked),
        sum(1 for passage in ranked if passage.origin == "graph"),
    )
    return ranked


def _output(ranked: list[Passage]) -> dict:
    missing_internal = not any(passage.policy_type == "INTERNAL_RULE" for passage in ranked)
    return {
        "count": len(ranked),
        "chunk_ids": [str(passage.chunk_id) for passage in ranked],
        "policy_version_ids": sorted({str(passage.policy_version_id) for passage in ranked}),
        "missing_internal_rule": missing_internal,
        "evidence": [{"chunk_id": str(item.chunk_id), "rerank_score": item.rerank_score,
                      "facet_scores": dict(item.facet_scores), "quality": item.retrieval_status,
                      "gaps": list(item.evidence_gaps)} for item in ranked],
        "retrieval": retrieval_mode(ranked),
        "graph_provenance": [
            {
                "chunk_id": str(passage.chunk_id),
                "edges": [
                    {
                        "seed_chunk_id": str(edge.seed_chunk_id),
                        "source_chunk_id": str(edge.source_chunk_id),
                        "target_chunk_id": str(edge.target_chunk_id),
                        "rule": edge.rule,
                        "confidence": edge.confidence,
                    }
                    for edge in passage.graph_edges
                ],
            }
            for passage in ranked
            if passage.origin == "graph"
        ],
    }
