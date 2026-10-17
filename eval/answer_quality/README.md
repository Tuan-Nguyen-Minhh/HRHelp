# Assessment and answer quality

This benchmark evaluates the production recommendation graph with **fixed evidence**.
It captures the structured assessment, full report, and short Vietnamese chat answer.
It does not measure retrieval, routing, persistence, or end-to-end chat.

`golden.json` contains 10 draft cases: five existing DOCX case scenarios and five
paired empty-evidence scenarios. Original documents and the existing reference
snapshot are pinned by SHA-256. Inputs contain facts and evidence only; expected
labels and reference answers are never passed to the application model.
Snapshot passages are fixture inputs, not claims about current law or live retrieval.

The source cases cover absence, lateness, delayed reporting, leaving a workstation,
and PPE compliance. Their labels deliberately require uncertainty or unsupported
sanctions. This initial suite does **not** establish accuracy on fully supported
sanctions, contradictory evidence, or multi-turn conversations. Add expert-reviewed
positive and conflict cases before using the results as a release gate.

## Run

Use the application Python environment from the repository root:

```bash
python -m eval.answer_quality.evaluate --validate-only

# Calls the configured application model; no business database writes.
python -m eval.answer_quality.evaluate --live --allow-draft \
  --output-dir eval/answer_quality/results/run_01

# Re-score saved outputs without API calls.
python -m eval.answer_quality.evaluate --allow-draft \
  --captures eval/answer_quality/results/run_01/captures.json \
  --output-dir eval/answer_quality/results/rescore_01

# Optional semantic evaluation of both report and chat answer.
# Install eval/case_assessment/requirements.txt and configure the judge API key.
python -m eval.answer_quality.evaluate --allow-draft \
  --captures eval/answer_quality/results/run_01/captures.json \
  --judge openrouter --judge-model PROVIDER/MODEL \
  --output-dir eval/answer_quality/results/judged_01
```

The judge supports the same providers as the existing RAGAS evaluator. Specify an
accessible model ID. Application generation and judge configuration are independent.
Each capture is checkpointed; `--live` starts a fresh capture. Use a new output
directory for each run. `--timeout` limits each generation and metric evaluation.

## Metrics and artifacts

- `captures.json`: actual model outputs, timestamp, case digest, and generation errors.
- `scores.json`: case-level deterministic checks and pass/fail.
- `summary.json`: scored coverage, failures, pass rate among scored cases, dataset digest.
- `report.md`: readable list of failed checks.
- `semantic_scores.json`: optional RAGAS faithfulness and factual correctness, separately
  for the report and answer. Failures are null with diagnostics, never zero.

Deterministic checks cover expected assessment status and sanction, preservation of
confirmed facts, missing fact keys, invented values for explicitly unknown facts,
verbatim citation integrity against supplied passages, and human-review safeguards.
Fact comparisons are exact and may flag harmless paraphrases; inspect failures.
Citation integrity checks spans, not whether a quote logically supports a conclusion.
Semantic scoring complements these checks; it is not expert legal validation.
The expected `checks` list records additional qualitative review criteria; these are
not individually scored by the deterministic runner.

Missing, stale, and operationally failed captures are excluded from the pass-rate
denominator and explicitly counted as incomplete coverage. They cannot yield a
successful CLI exit. Exit 0 requires complete deterministic passes and, if requested,
complete semantic scoring. **There is no semantic score threshold**; inspect those
scores separately. Empty-evidence cases expect a normal fallback, not an LLM error.

## Review and rebuild

Review expected status/sanction, unknown facts, reference report, and reference answer
against each source and the pinned snapshot. Record approvals in `review_status`
per case and at dataset level. Until then, evaluation requires `--allow-draft`.

```bash
python -m eval.answer_quality.build_dataset
```

Rebuilding overwrites draft labels, including manual edits. Source metadata is reused
without modification; its old `tested_golden_dataset/` paths are mapped to the
current `golden_dataset/` directory and the original file hashes are verified.
Keep approved labels under version control before rebuilding. Never add the golden
answers to the retrieval corpus.
