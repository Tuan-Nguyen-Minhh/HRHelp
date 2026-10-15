"""Hybrid candidates → seed rerank → citations → facet rerank → evidence selection.

One targeted retrieval retry can fill a missing source layer. API failures are
explicitly degraded and never masquerade as successful semantic ranking.
"""

import asyncio
import logging
import operator
from collections.abc import Awaitable
from dataclasses import replace
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.core.config import settings
from src.features.cite.model.evidence import select_evidence
from src.features.cite.model.graph_expand import expand_node
from src.features.cite.model.page_index import anchors_for, select_article_heads
from src.features.cite.model.passage import Passage
from src.features.cite.model.query import SearchQuery, act_text, facet_queries
from src.features.cite.model.rank import rank_passages
from src.features.cite.model.rerank import rerank
from src.features.cite.model.rrf import reciprocal_rank_fusion
from src.features.cite.model.similarity import similarity_passages
from src.features.cite.model.store import fetch_article_index, fetch_by_bm25, fetch_candidates, to_passage
from src.features.cite.model.terms import search_terms

logger = logging.getLogger(__name__)
RETRIEVAL_K = 8  # outline fallback compatibility; candidate/final limits live in settings
_INDEX_POOL = 80


class RetrievalState(TypedDict, total=False):
    query: SearchQuery
    terms: list[str]
    similarity: list[Passage]
    bm25: list[Passage]
    lexical: list[Passage]
    fused: list[Passage]
    seeds: list[Passage]
    seed_status: str
    expanded: list[Passage]
    hits: list[Passage]
    retrieval: str
    rerank_status: str
    evidence_gaps: list[str]
    evidence_size: int
    evidence_size_unit: str
    supplemented: bool
    graph_status: str
    trace: dict
    arm_status: Annotated[dict[str, str], operator.or_]


def build_retrieval_graph(session) -> CompiledStateGraph:
    # A single AsyncSession cannot execute concurrent SQL commands. Each arm
    # keeps its own failure savepoint and shares a lock around database work.
    db_lock = asyncio.Lock()

    async def locked_arm(name, operation):
        async with db_lock:
            try:
                async with session.begin_nested():
                    return {name: await operation(), "arm_status": {name: "OK"}}
            except Exception as exc:
                logger.warning("retrieval arm failed arm=%s error=%s", name, type(exc).__name__)
                return {name: [], "arm_status": {name: type(exc).__name__}}

    async def similarity(state):
        original = state["query"]
        focused = act_text(original)
        query = replace(original, text=focused, embedding=original.embedding if focused == original.text else None)
        return await locked_arm("similarity", lambda: similarity_passages(session, query, settings.RETRIEVAL_CANDIDATE_K))

    async def bm25(state):
        return await locked_arm("bm25", lambda: _bm25(session, state))

    async def lexical(state):
        return await locked_arm("lexical", lambda: _lexical(session, state))

    async def supplement(state):
        # A bounded extra sparse search for the source layer missed in the first
        # pass, using the conduct plus that layer's needs, not a desired sanction.
        pools = [state.get("expanded") or state.get("fused") or []]
        for role in ("internal_rule", "authority"):
            if f"MISSING_{role.upper()}" not in state.get("evidence_gaps", []):
                continue
            terms = search_terms(state["query"].family, [], facet_queries(state["query"])[role])
            async with db_lock:
                try:
                    async with session.begin_nested():
                        rows = await fetch_by_bm25(session, state["query"].incident_date, terms,
                                                   settings.RETRIEVAL_CANDIDATE_K,
                                                   policy_types=("INTERNAL_RULE",) if role == "internal_rule" else
                                                   ("LAW", "DECREE", "CIRCULAR"))
                    from src.features.cite.model.evidence import source_role
                    pools.append([item for item in rows if source_role(item) == role])
                except Exception as exc:
                    logger.warning("retrieval supplement failed role=%s error=%s", role, type(exc).__name__)
        combined = {item.chunk_id: item for pool in pools for item in pool}
        return {"expanded": list(combined.values()), "supplemented": True}

    async def page_index(state):
        return await _page_index(session, state)

    return compile_retrieval(similarity, bm25, lexical, page_index, expand_node(session), supplement)


def compile_retrieval(similarity, bm25, lexical, page_index=None, expand=None, supplement=None,
                      reranker=None) -> CompiledStateGraph:
    ranker = reranker or rerank

    async def seed_node(state):
        result = await ranker(act_text(state["query"]), list(state.get("fused") or []))
        return {"seeds": result.passages[:5] if result.status == "OK" else [],
                "seed_status": result.status,
                "trace": {"seed_rerank": _ranking(result.passages), "seed_error": result.error}}

    async def final_node(state):
        pool = list(state.get("expanded") or state.get("fused") or [])
        scores = {}
        errors = {}
        status = state.get("seed_status", "FAILED")
        if state.get("graph_status") == "FAILED":
            status = "FAILED"
            errors["graph"] = "GRAPH_EXPANSION_FAILED"
        if status == "OK" and pool:
            semaphore = asyncio.Semaphore(2)

            async def score(role, query_text):
                async with semaphore:
                    return role, await ranker(query_text, pool)

            results = await asyncio.gather(*[score(role, text) for role, text in facet_queries(state["query"]).items()])
            for role, result in results:
                if result.status != "OK":
                    status = result.status
                    errors[role] = result.error
                scores[role] = {item.chunk_id: item.rerank_score or 0 for item in result.passages}
            pool = [replace(item, rerank_score=max(values[item.chunk_id] for values in scores.values()),
                            facet_scores=tuple((role, values[item.chunk_id]) for role, values in scores.items()))
                    for item in pool]
            pool.sort(key=lambda item: max(score for _, score in item.facet_scores), reverse=True)
        try:
            selected = select_evidence(pool, status=status)
        except Exception as exc:
            # An invalid tokenizer/budget config must not fail open.
            logger.warning("evidence selection failed error=%s", type(exc).__name__)
            return {"hits": [replace(item, retrieval_status="DEGRADED", evidence_gaps=("EVIDENCE_SELECTION_FAILED",))
                             for item in pool[:settings.RETRIEVAL_FINAL_K]],
                    "rerank_status": "FAILED", "evidence_gaps": ["EVIDENCE_SELECTION_FAILED"],
                    "retrieval": "hybrid" if pool else "empty"}
        trace = dict(state.get("trace") or {})
        trace.update({"facet_rerank": {role: [{"chunk_id": str(key), "score": value} for key, value in values.items()]
                                      for role, values in scores.items()}, "rerank_errors": errors,
                      "selected": [str(item.chunk_id) for item in selected.passages],
                      "omitted": [str(item.chunk_id) for item in pool if item.chunk_id not in
                                  {hit.chunk_id for hit in selected.passages}]})
        return {"hits": selected.passages, "rerank_status": status, "evidence_gaps": list(selected.gaps),
                "evidence_size": selected.size, "evidence_size_unit": selected.size_unit,
                "trace": trace, "retrieval": "hybrid" if selected.passages else "empty"}

    def after_final(state):
        if (supplement is not None and state.get("rerank_status") == "OK" and not state.get("supplemented")
                and any(gap in {"MISSING_INTERNAL_RULE", "MISSING_AUTHORITY"} for gap in state.get("evidence_gaps", []))):
            return "supplement"
        if not state.get("hits") and not state.get("fused"):
            return "page_index"
        return "done"

    graph = StateGraph(RetrievalState)
    for name, node in (("similarity", similarity), ("bm25", bm25), ("lexical", lexical), ("rrf", rrf_node),
                       ("seed_rerank", seed_node), ("expand", expand or _passthrough_expand),
                       ("rerank", final_node), ("page_index", page_index or _abstain)):
        graph.add_node(name, node)
    if supplement is not None:
        graph.add_node("supplement", supplement)
        graph.add_edge("supplement", "rerank")
    for arm in ("similarity", "bm25", "lexical"):
        graph.add_edge(START, arm)
    graph.add_edge(["similarity", "bm25", "lexical"], "rrf")
    graph.add_edge("rrf", "seed_rerank")
    graph.add_edge("seed_rerank", "expand")
    graph.add_edge("expand", "rerank")
    routes = {"done": END, "page_index": "page_index"}
    if supplement is not None:
        routes["supplement"] = "supplement"
    graph.add_conditional_edges("rerank", after_final, routes)
    graph.add_edge("page_index", END)
    return graph.compile()


def rrf_node(state):
    rankings = [list(state.get(name) or []) for name in ("similarity", "bm25", "lexical")]
    return {"fused": reciprocal_rank_fusion(rankings, settings.RETRIEVAL_FUSION_K)}


def _ranking(passages):
    return [{"chunk_id": str(item.chunk_id), "rrf_score": item.score, "rerank_score": item.rerank_score}
            for item in passages]


def _passthrough_expand(state):
    return {"expanded": list(state.get("fused") or [])}


async def _abstain(_state):
    return {"hits": [], "retrieval": "empty"}


async def _page_index(session, state):
    query = state["query"]
    phrases = list(anchors_for(query.family))
    try:
        rows = await fetch_article_index(session, query.incident_date, phrases, _INDEX_POOL)
    except Exception:
        logger.exception("page_index retriever failed")
        return {"hits": [], "retrieval": "empty"}
    hits = select_article_heads(rows, phrases, RETRIEVAL_K)
    return {"hits": hits, "retrieval": "page_index" if hits else "empty"}


async def _bm25(session, state):
    query = state["query"]
    # Source cohorts are searched before limiting, so an abundant internal-rule
    # corpus cannot crowd all law out of the candidate pool (or vice versa).
    pools = []
    for role, types in (("internal_rule", ("INTERNAL_RULE",)), ("authority", ("LAW", "DECREE", "CIRCULAR"))):
        terms = search_terms(query.family, query.fact_lines, facet_queries(query)[role])
        pools.append(await fetch_by_bm25(session, query.incident_date, terms,
                                        settings.RETRIEVAL_CANDIDATE_K, policy_types=types))
    return reciprocal_rank_fusion(pools, settings.RETRIEVAL_CANDIDATE_K)


async def _lexical(session, state):
    query = state["query"]
    terms = search_terms(query.family, query.fact_lines, act_text(query))
    rows = await fetch_candidates(session, query.incident_date, terms)
    return rank_passages([to_passage(hit) for hit in rows], terms, settings.RETRIEVAL_CANDIDATE_K)


async def _arm(name: str, awaitable: Awaitable[list[Passage]]) -> dict:
    try:
        return {name: await awaitable}
    except Exception:
        logger.exception("%s retriever failed", name)
        return {name: []}
