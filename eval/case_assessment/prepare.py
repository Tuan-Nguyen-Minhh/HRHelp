"""Merge captured RAG results into the draft dataset without fabricating runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def prepare(runs: list[dict], *, facts_for_faithfulness: bool = False) -> list[dict]:
    base = json.loads((HERE / "ragas_dataset.json").read_text(encoding="utf-8"))
    manifest = json.loads((HERE / "source_metadata.json").read_text(encoding="utf-8"))
    expected_ids = manifest["case_ids_in_row_order"]
    if not isinstance(runs, list) or any(not isinstance(run, dict) for run in runs):
        raise ValueError("Captured runs must be a JSON list of objects")
    ids = [run.get("case_id") for run in runs]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case_id in captured runs")
    if set(ids) != set(expected_ids):
        raise ValueError(f"Expected exactly {expected_ids}; received {ids}")
    indexed = {run["case_id"]: run for run in runs}
    for case_id, sample in zip(expected_ids, base, strict=True):
        run = indexed[case_id]
        response = run.get("response")
        contexts = run.get("retrieved_contexts")
        if not isinstance(response, str) or not response.strip():
            raise ValueError(f"{case_id}: response must be the nonempty actual assessment report")
        if not isinstance(contexts, list) or any(not isinstance(c, str) or not c.strip() for c in contexts):
            raise ValueError(f"{case_id}: retrieved_contexts must be the actual list of passage strings; [] is valid for an empty retrieval")
        if run.get("user_input") != sample["user_input"]:
            raise ValueError(f"{case_id}: captured user_input differs from the fixture; review the input and reference together")
        sample["response"] = response
        sample["retrieved_contexts"] = list(contexts)
        if facts_for_faithfulness:
            sample["retrieved_contexts"].append(
                "[Supporting case input; not a retrieved policy document]\n" + sample["user_input"]
            )
    return base


def load_dataset(path: str | Path | None = None):
    """Load a RAGAS EvaluationDataset. Draft samples may have null run fields."""
    from ragas import EvaluationDataset

    rows = json.loads(Path(path or HERE / "ragas_dataset.json").read_text(encoding="utf-8"))
    return EvaluationDataset.from_list(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "ragas_dataset.completed.json")
    parser.add_argument("--facts-for-faithfulness", action="store_true",
                        help="Append supplied case input as supporting context; use this output only for grounding, not retrieval metrics")
    args = parser.parse_args()
    rows = prepare(json.loads(args.runs.read_text(encoding="utf-8")), facts_for_faithfulness=args.facts_for_faithfulness)
    from ragas import EvaluationDataset

    EvaluationDataset.from_list(rows)  # Verify the actual installed RAGAS schema.
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(rows)} samples to {args.output}")
    if args.facts_for_faithfulness:
        print("Supporting case input included: do not use this output for retrieval precision/recall.")


if __name__ == "__main__":
    main()
