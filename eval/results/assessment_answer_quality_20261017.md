# Evaluation run — 17 October 2026

Fresh production outputs generated with DeepSeek (`deepseek-flash`); final RAGAS judge: Mistral (`ministral-8b-2512`). Labels remain drafts pending expert review.

## Coverage

- Answer quality: 10/10 captured and scored; all 40 semantic scores present. Deterministic checks pass 5/10: source cases 0/5, empty-evidence cases 5/5.
- Case assessment: 5/5 live retrieval outputs; all 20 metric scores present. One HTTP 503 recovered through retry.
- The answer-quality CLI exits 1 because golden checks fail, not because the run is incomplete. Case-assessment CLI exits 0.

## Answer quality

Fixed evidence; this does not evaluate live retrieval or end-to-end conversation.

| Output / metric | All 10 | Source cases (5) | Empty evidence (5) |
| --- | ---: | ---: | ---: |
| report / faithfulness | 0.784 | 0.785 | 0.783 |
| report / factual_correctness | 0.746 | 0.618 | 0.874 |
| answer / faithfulness | 0.720 | 0.584 | 0.857 |
| answer / factual_correctness | 0.785 | 0.570 | 1.000 |

Deterministic failures:

- CA01: incomplete missing-fact coverage.
- CA02–CA04: WARNING proposed despite the draft reference expecting no selected sanction; incomplete missing-fact coverage.
- CA05: NEED_MORE_FACTS / WARNING differs from draft NOT_SUPPORTED / no sanction; incomplete missing-fact coverage.
- All source cases pass confirmed-fact preservation, no invented explicitly unknown facts, citation integrity, and human-review/ticket safeguards.
- Missing-fact checks compare exact keys. Inspect the source capture before treating these omissions as semantic failures. Citation integrity establishes verbatim spans, not correctness of legal reasoning.

## Live case assessment

| Metric | Mean | Scored |
| --- | ---: | ---: |
| faithfulness | 0.889 | 5/5 |
| factual_correctness | 0.532 | 5/5 |
| context_precision | 0.924 | 5/5 |
| context_recall | 0.816 | 5/5 |

## Run notes

Nullable fixture headings initially failed input validation; normalized to empty strings and regenerated every answer-quality output. Regression tests: 3 passed.

DeepSeek judging was interrupted after repeated truncated completions, including an increased-output-allowance attempt. Final Mistral judging reused the saved production outputs. Golden expectations were not changed to improve scores.

## Artifacts

- [Answer-quality diagnostics](../answer_quality/results/run_20261017T030843Z/report.md)
- [Answer-quality semantic scores](../answer_quality/results/run_20261017T030843Z/semantic_scores.json)
- [Case-assessment report](../case_assessment/results/run_20261017T030843Z/report.md)
- [Case-assessment scores](../case_assessment/results/run_20261017T030843Z/scores.json)
