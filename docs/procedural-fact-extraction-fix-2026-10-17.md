# Procedural fact extraction: repeated questions after completed answers

## Diagnosis

The reported conversation correctly selected `fact_planner` (`updates_case_fact=true`, semantic recheck confirmed). The planner completed without a fallback. The application logs at 06:50–06:51 UTC showed `ambiguous=minutes_made,explanation_requested`; those facts were absent from storage. Thus this failure was downstream of intent routing.

The deterministic regression command was:

```sh
.venv/bin/pytest tests/test_procedural_fact_extraction.py -q
```

Before the fix, the original screenshot wording with two valid structured `true` facts produced `merged={}`, both keys in `missing_keys`, and both in `ambiguities`. Removing only the leading label from each evidence span made the old canonicalizer accept the same value. The old `_flag(evidence)` parser recognized a limited sentence prefix and globally searched for “chưa”, so labeled/passive wording and unrelated negative clauses could disagree with an otherwise correct semantic value.

## Change

- The LLM remains responsible for the meaning of procedural statements. Python normalizes the returned flag value and validates that its evidence occurs in original user-provided sources, rather than trying to re-extract sentence meaning with a second keyword parser.
- Sources are the current original USER message, the case's user-supplied description, and recent original business USER turns. Assistant messages, generated summaries, help/casual exchanges and internal messages are not substituted for evidence.
- Source matching normalizes Unicode, casing and whitespace. Empty/unsupported values, absent evidence, low confidence and explicitly ambiguous facts are still rejected.
- Explicit key/value parsing and deterministic fallback read the current user message, so historical literal lines cannot overwrite a newer semantic correction.
- Existing business memory supplies the original user sources so already-provided answers can be read on a continuation. No graph node/edge, route selection rule, database schema or workflow authority was added.
- Planner prompt version: `clarify-planner-v7-grounded-procedural-facts`; it requests verbatim user evidence and distinguishes a completed request from an employee response still pending.

Evidence membership establishes provenance, not independently proven semantic correctness. The model still determines the relationship between the user's wording and the flag; regression and live checks cover the reported failure without claiming universal extraction accuracy.

## Validation

- Original failing test now passes. The targeted file has 12 tests covering labeled/passive wording, independent negative clauses, false values, source rejection, prior-user recovery, current-value precedence and ambiguous/low-confidence input.
- 238 related regression tests passed; Ruff and `git diff --check` passed.
- Three PostgreSQL integration tests passed with all synthetic data rolled back. The new test goes through `_planned` → graph extraction → validation → real SQL persistence and verifies both flags have the original source message/actor and are absent from the next projection's missing fields.
- Six synthetic live cases passed, including the exact reported wording, passive voice, sent-but-unanswered requests, mixed true/false states, uncompleted procedures and future plans explicitly not completed. Router selection for the reported wording remains `fact_planner`. Results are recorded in `eval/routing/procedural-fact-results.json`; these are smoke checks, not a broad accuracy evaluation.
- One additional live continuation ("Tôi đã cung cấp hai thông tin ở trên rồi, hãy tiếp tục lập biên bản") recovered both `true` values from original user history and left neither key missing, without a planner fallback.

No existing case facts were changed by diagnostics or smoke tests.
