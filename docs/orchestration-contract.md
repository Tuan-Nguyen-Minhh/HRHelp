# Shared conversation contract

The case orchestrator owns conversation progress. Branch agents propose facts,
answers and actions; they do not replace durable memory with their response.
The executable policy is `src/agents/conversation.py`.

## State and updates

- `pending_action` identifies the outstanding workflow, independently of the current route.
- `pending_fact_keys` and `open_questions` describe its unanswered inputs.
- `working_state` persists the validated family and complete fact schema: keys,
  labels, questions, required flags and provenance. Historical facts remain in
  the case fact store. A short textual summary is supplementary context.
- Each graph result has a `state_update`: `preserve` or `progress`. All routing
  baselines preserve state. Validated extraction can produce progress. An
  extraction failure without accepted facts preserves state too.
- `memory_patch` is the only policy that decides changes to workflow memory.
  Absent patch fields keep their old values. A side answer never clears the
  pending workflow, schema, questions or validated summary.
- `task_change` describes an explicit request to keep, replace or cancel the
  workflow. Cancellation requires a successful, sufficiently confident router
  result; it clears pending work, not case facts. A new supported workflow goal
  replaces the previous pending action after validation. Completion is recorded
  by the service after the action succeeds, not by an LLM claim.

Preparation actions are registered once in `WORKFLOW_ACTIONS`. They pass through
fact validation even if the model omits `requires_fact_planner`. Reading a saved
assessment does not need this step. Resumption uses the same registry and
validated fact/confirmation intent for every workflow; no special rule is needed
for the wording or incident type of a particular user reply. A side question can
be answered while another workflow remains pending.

## Failure and context rules

Invalid structured model output is `IntentFallback.OUTPUT`, not evidence of an
unclear user goal. If questions are pending, the orchestrator asks the planner to
validate the reply before resuming anything. Without pending inputs, it reports
a processing error and preserves state. A genuine ambiguous intent can still
ask the user to clarify. Network failures retain the existing fact-planner
fallback, subject to the same update policy.

The latest user turn is supplied separately from historical context. Both router
and planner receive the shared semantic contract. Important facts and the active
schema are structured inputs; prompts no longer discard the beginning of that
context at an arbitrary character boundary. Recent conversational messages use
a soft character budget and omit whole old messages instead of cutting each
user reply at 500/1000 characters. Internal status/tool handoffs do not occupy
the recent conversation window. The latest message is kept whole even when it
exceeds the soft budget; the provider's overall context limit still applies.

Read requests with no new user message project the stored state without running
the semantic router. Retrieval handoffs likewise retain the already validated
schema and confirmed optional facts instead of reinterpreting old conversation
text against a fresh catalog template.

## Persistence and verification

Migration `0012_conversation_working_state` adds one JSONB column with an empty
default; it does not rewrite old facts or invent missing historical schema.
Existing conversations use their pending keys until a validated plan persists
the full schema. Apply the migration before starting the updated backend.

`tests/test_conversation_contract.py` exercises recovery from actual parser
exceptions, all registered workflows, side routes, both models failing, task
replacement/cancellation, immutable schema requirements, and long user replies.
These use local doubles, without sending case content to external models.
