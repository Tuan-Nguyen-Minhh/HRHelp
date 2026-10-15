"""Capture live retrieval and measure held-out, expert-labelled evidence bundles.

No database writes are needed. Without --generate, evaluation is entirely offline.
"""

import argparse
import asyncio
import json
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class CaseReference(BaseModel):
    case_id: str
    reference_status: str
    incident_date: date
    family: str = "GENERAL"
    description: str
    facts: dict[str, str] = Field(default_factory=dict)
    # Each inner list is one complete acceptable set of supporting chunks.
    evidence_bundles: list[list[UUID]]
    critical_chunk_ids: list[UUID] = Field(default_factory=list)
    relevance: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def complete_reference(self):
        if not self.evidence_bundles or any(not bundle for bundle in self.evidence_bundles):
            raise ValueError("Expert references must include at least one nonempty evidence bundle")
        if any(value < 0 or value > 3 for value in self.relevance.values()):
            raise ValueError("Graded relevance must be between 0 and 3")
        return self


def load_references(path):
    cases = [CaseReference.model_validate(row) for row in json.loads(Path(path).read_text())]
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Duplicate case_id in references")
    if any(case.reference_status != "expert_reviewed" for case in cases):
        raise ValueError("References are drafts; HR/legal must review them before reporting accuracy")
    return cases


def measures(reference, run):
    import math

    selected = list(dict.fromkeys(run["selected_ids"]))
    candidates = set(run["candidate_ids"])
    bundles = [set(map(str, bundle)) for bundle in reference.evidence_bundles]
    gold = set.union(*bundles)
    selected_set = set(selected)
    # Alternatives are scored separately; requiring the union would penalize a
    # complete valid alternative for omitting redundant evidence from another.
    candidate_recall = max(len(bundle & candidates) / len(bundle) for bundle in bundles)
    final_recall = max(len(bundle & selected_set) / len(bundle) for bundle in bundles)
    critical = set(map(str, reference.critical_chunk_ids))
    graded = reference.relevance or {chunk_id: 3 for chunk_id in gold}
    def dcg(values):
        return sum((2 ** value - 1) / math.log2(rank + 2) for rank, value in enumerate(values))
    ideal = dcg(sorted(graded.values(), reverse=True)[:len(selected)])
    return {
        "candidate_recall": candidate_recall,
        "final_recall": final_recall,
        "precision": len(gold & selected_set) / len(selected) if selected else 0,
        "complete_bundle": any(bundle <= selected_set for bundle in bundles),
        "critical_recall": len(critical & selected_set) / len(critical) if critical else None,
        "ndcg": dcg([graded.get(chunk_id, 0) for chunk_id in selected]) / ideal if ideal else 0,
        "rerank_ok": run.get("rerank_status") == "OK",
        "evidence_gaps": run.get("evidence_gaps", []),
        "latency_ms": run.get("latency_ms"),
    }


async def generate(cases, output):
    # Loaded only for live generation: offline evaluation needs no DB/API credentials.
    import time

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from src.core.config import settings
    from src.features.cite.model.pipeline import build_retrieval_graph
    from src.features.cite.model.query import SearchQuery
    from src.features.cite.model.terms import search_terms

    if not settings.COHERE_API_KEY.strip():
        raise ValueError("Fill COHERE_API_KEY in .env before live retrieval evaluation")
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI)
    session_factory = async_sessionmaker(engine)
    runs = {}
    try:
        for case in cases:
            query = SearchQuery(case.description, case.incident_date, uuid4(), case.family,
                                [f"{key}: {value}" for key, value in case.facts.items()], case.description)
            started = time.perf_counter()
            async with session_factory() as session:
                state = await build_retrieval_graph(session).ainvoke({
                    "query": query, "terms": search_terms(query.family, query.fact_lines, query.description)})
            candidates = list({str(item.chunk_id) for name in ("fused", "expanded") for item in state.get(name, [])})
            runs[case.case_id] = {
                "candidate_ids": candidates,
                "selected_ids": [str(item.chunk_id) for item in state.get("hits", [])],
                "rerank_status": state.get("rerank_status"), "evidence_gaps": state.get("evidence_gaps", []),
                "trace": state.get("trace", {}), "latency_ms": round((time.perf_counter() - started) * 1000),
                "model": settings.COHERE_RERANK_MODEL,
                "evidence_size": state.get("evidence_size"), "evidence_size_unit": state.get("evidence_size_unit"),
            }
            # Checkpoint each completed case; never lose all paid calls on interruption.
            output.write_text(json.dumps(runs, ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()
    return runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", required=True)
    parser.add_argument("--runs", help="Captured retrieval JSON to evaluate offline")
    parser.add_argument("--generate", action="store_true", help="Call live DB, embeddings and Cohere")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--output-dir", default="eval/retrieval/results")
    args = parser.parse_args()
    cases = load_references(args.references)
    if args.validate_only:
        print(f"Validated {len(cases)} expert-reviewed references. Database identities not yet checked.")
        return
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if args.generate:
        runs = asyncio.run(generate(cases, output / "runs.json"))
    elif args.runs:
        runs = json.loads(Path(args.runs).read_text())
    else:
        parser.error("Choose --generate or --runs, or use --validate-only")
    missing = [case.case_id for case in cases if case.case_id not in runs]
    if missing:
        raise ValueError(f"Missing captured runs: {missing}")
    scores = {case.case_id: measures(case, runs[case.case_id]) for case in cases}
    averages = {metric: sum(row[metric] for row in scores.values()) / len(scores)
                for metric in ("candidate_recall", "final_recall", "precision", "complete_bundle", "ndcg", "rerank_ok")}
    (output / "scores.json").write_text(json.dumps({"sample_count": len(cases), "averages": averages,
                                                 "cases": scores}, ensure_ascii=False, indent=2))
    print(json.dumps({"sample_count": len(cases), "averages": averages}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
