"""Run the retrieval graph and audit it on the agent ledger.

The graph runs three search arms, then RRF, hop-1 graph expansion, and rerank.
An empty rerank walks the article outline before the handoff is packed.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.runs import RetrievalHit, begin_search, complete_search, save_retrievals
from src.features.cite.model.page_index import retrieval_mode
from src.features.cite.model.passage import Passage
from src.features.cite.model.pipeline import build_retrieval_graph
from src.features.cite.model.query import SearchQuery
from src.features.cite.model.terms import search_terms


async def search_policies(session: AsyncSession, query: SearchQuery) -> list[Passage]:
    """Run the retrieval sub-agent and return the passages the handoff may carry."""
    terms = search_terms(query.family, query.fact_lines, query.description)
    tool = await begin_search(
        session,
        query.agent_run_id,
        {
            "query": query.text,
            "incident_date": query.incident_date.isoformat(),
            "terms": terms,
            "retrievers": ["similarity", "bm25", "lexical", "page_index"],
            "expansion": "graph_hop1",
        },
    )
    graph = build_retrieval_graph(session)
    state = await graph.ainvoke({"query": query, "terms": terms})
    ranked = list(state.get("hits") or [])
    await complete_search(session, tool, _output(ranked))
    await save_retrievals(
        session,
        query.agent_run_id,
        [RetrievalHit(passage.chunk_id, passage.score, passage.origin or "hybrid") for passage in ranked],
    )
    return ranked


def _output(ranked: list[Passage]) -> dict:
    missing_internal = not any(passage.policy_type == "INTERNAL_RULE" for passage in ranked)
    return {
        "count": len(ranked),
        "chunk_ids": [str(passage.chunk_id) for passage in ranked],
        "policy_version_ids": sorted({str(passage.policy_version_id) for passage in ranked}),
        "missing_internal_rule": missing_internal,
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
