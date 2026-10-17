# Semantic conversation context for short-term memory

Research date: 2026-10-17. Scope: connect a user's current question to earlier USER questions and ASSISTANT answers while preserving P-029's existing graph and routing responsibilities.

## Finding

Use a bounded LLM dialogue-interpretation step alongside the existing deterministic memory. It should describe the semantic relationship between turns, the current goal, resolved references, corrections, and open questions. Feed this advisory context to the existing router and answer generation. Keep the original user message, raw recent turns, and authoritative case/workflow state available separately.

This is a design recommendation for this repository, not a claim that a generic summary or an extra model call guarantees correct understanding.

## What primary sources establish

### Context-dependent questions need reference resolution

CANARD defines question-in-context rewriting as converting a context-dependent question into a self-contained question with the same answer. Its motivation explicitly includes coreference and ellipsis: understanding a follow-up can require earlier questions and answers. This supports representing what “cái đó”, “bước tiếp theo”, or “cần những gì” refers to, rather than merely concatenating messages. The paper does not establish that any particular prompt or model will solve Vietnamese HR conversations. [Elgohary et al., *Can You Unpack That?*, EMNLP-IJCNLP 2019](https://aclanthology.org/D19-1605/).

QReCC separates question rewriting, retrieval, and reading comprehension as evaluable parts of conversational QA. This supports testing the interpretation of the current question separately from the final answer; a fluent answer is insufficient evidence that context was understood. QReCC is an open-domain benchmark, so its reported performance should not be transferred to this application. [Anantha et al., *Open-Domain Question Answering Goes Conversational via Question Rewriting*, NAACL 2021](https://aclanthology.org/2021.naacl-main.44/).

### Short-term memory must remain conversation-scoped and bounded

LangChain describes short-term memory as history within one thread/conversation, separated from other threads. It warns that long histories can include distracting stale/off-topic content, incur more cost and latency, and exceed model limits. It documents trimming and LLM summarization as alternatives, while noting that removing messages may lose information. These are relevant principles; adopting its middleware or replacing this application's graph is unnecessary. [LangChain, *Short-term memory*](https://docs.langchain.com/oss/python/langchain/short-term-memory).

LangMem's running-summary API records both the summary and IDs of already summarized messages, including the last processed ID. It incorporates existing summaries when processing new messages and retains a recent-message portion. Its documentation also distinguishes a summary token *budget* from an enforced model output limit. These details support an explicit checkpoint cursor, raw-turn retention, and independent input/output limits in P-029. They do not require adding LangMem as a dependency. [LangMem, *Short Term Memory API Reference*](https://langchain-ai.github.io/langmem/reference/short_term/).

### Compression is useful but lossy

Anthropic describes compaction as retaining critical conversation information in a smaller context, and structured notes as retaining progress/dependencies outside the active context. It warns that aggressive compression can discard subtle context needed later, recommends testing complex traces, and advises prompts at a useful level of detail rather than brittle exhaustive rules. This supports a concise structured projection plus recent source messages, with targeted evaluation. It is engineering guidance rather than a proof that recursively summarized memories preserve all meaning. [Anthropic, *Effective context engineering for AI agents*](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).

## Repository observations

At inspection, `src/features/clarify/model/memory.py` builds a deterministic context from case profile, working facts, workflow memory, and recent business messages. Its `_summary` contains task/fact fields and the last assistant text, but does not analyze how questions and answers relate. `side_context` keeps help and general messages in separate lists. Those lists alone cannot describe chronology across scopes. [Local source](../src/features/clarify/model/memory.py).

Standalone chat already passes visible conversation history to the shared graph. Q&A formatting receives selected approved answer text and bounded memories, but these inputs do not provide an explicit semantic interpretation. [Standalone service](../src/features/standalone_chat/service.py), [Q&A formatter](../src/features/clarify/model/help_reply.py).

## Proposed integration

Everything below is a repo-specific design inference informed by the sources, not a prescribed external architecture.

1. After conversation ownership is established and the current user message is saved, collect ordered visible USER/ASSISTANT turns from that conversation. Include stable message IDs, roles, scope/kind metadata, and bounded content. Exclude internal messages. Preserve cross-scope chronology for interpretation, but retain scope labels.
2. Load a bounded semantic checkpoint from earlier message metadata, if valid. Supply its previous semantic summary, the new/recent source turns, the latest original question, and compact authoritative case/workflow context as separately labeled inputs.
3. Make one bounded structured LLM call. Ask for the current goal, an interpreted self-contained question, topic continuity or shift, concise links between turns, corrections, and unresolved questions. Each nonempty interpretation must point to supplied source IDs. Where history supports several readings, preserve uncertainty instead of inventing one.
4. Validate the output schema, provenance IDs, roles, and chronology. Return a separate `dialogue_context` to existing consumers. Keep router decisions, fact extraction, pending actions, and workflow execution under their existing owners.
5. Save the successful bounded projection and `through_message_id` in message JSON metadata as a continuation checkpoint. This storage choice uses an existing repository capability and avoids a migration; it is not LangMem's storage model. Advance the cursor only through messages actually considered. Keep source messages intact.
6. On timeout, missing credentials, invalid structure/provenance, or unusable checkpoint, continue with the existing deterministic/raw context. Never substitute an old interpreted question for the new user question. A failed semantic refresh must not block the conversation or persist a falsely current checkpoint.

An illustrative context object:

```json
{
  "current_goal": {
    "text": "Tìm hiểu thông tin cần chuẩn bị để lập biên bản",
    "source_ids": ["u1", "a1", "u2"]
  },
  "interpreted_question": {
    "text": "Tôi cần chuẩn bị những thông tin gì để lập biên bản trên HR Help?",
    "source_ids": ["u1", "a1", "u2"]
  },
  "topic_transition": "follow_up",
  "links": [
    {
      "from_id": "u2",
      "to_id": "a1",
      "relation": "follow_up",
      "meaning": "Hỏi thông tin đầu vào sau khi đã được hướng dẫn nơi bắt đầu"
    }
  ],
  "corrections": [],
  "open_questions": []
}
```

This is an example contract, not an instruction to hardcode minutes vocabulary or match specific phrases. The LLM should infer the relationships from dialogue content.

## Meaning and authority boundaries

- Dialogue memory describes **what the participants mean and discuss**. Confirmed case facts and workflow state describe **what the application knows and has done**. Never merge the former directly into the latter.
- An assistant's earlier statement is evidence that it *said* something; it is not independent proof that the statement is true or an action occurred. Keep “assistant proposed creating minutes” distinct from “minutes were created”.
- A user correction may supersede an earlier *dialogue interpretation*. Any change to stored case facts, approvals, or pending tasks must still go through existing extraction/workflow rules.
- A request for instructions must retain its question modality. Do not turn “lập biên bản như nào?” into authorization to create one. Keep the latest original message canonical for execution intent.
- Source IDs establish traceability, not factual truth. Validate they belong to the authorized conversation and supplied inputs; a fabricated ID or a reference to another conversation invalidates that interpretation.
- Conversation text and previous summaries are untrusted data. Do not let quoted instructions alter the interpreter's system rules, select routes, call tools, or modify state.

## Pitfalls and mitigations

**Accumulated summary drift:** repeated summaries can retain an early mistake while dropping the correction or caveat. Preserve explicit corrections and uncertainty, validate retained source references against conversation-local messages, include recent raw pairs, and let the current original question override stale interpretation. Do not describe a checkpoint as a complete transcript. This mitigation is a design response to the documented lossiness of compaction, not a guarantee of semantic fidelity.

**Scope leak:** an off-topic social exchange should not become a case fact; a help question should not cancel a pending business action; context from another case/user should never enter the payload. Ownership checks and a conversation-local query are the isolation boundary. Scope labels and provenance make intra-conversation transitions inspectable; they are not substitutes for authorization.

**Partial history:** if a bounded window skips messages after the prior checkpoint, expose that gap rather than implying complete coverage. Keep cursor semantics honest. A restart or malformed checkpoint should recover from authorized recent source turns, not fail closed on the whole chat.

**Latency/cost:** an interpreter adds one inference on the request path. Bound input size, output size, total timeout, and retries; reuse the configured chat client and persist only validated context. The numerical limits should be measured against this deployment, not copied from a benchmark.

## Evaluation before rollout

Test interpretation and downstream behavior with Vietnamese multi-turn examples:

- Navigation guidance → “cần chuẩn bị những gì?” resolves to required input information, without repeating unrelated navigation steps.
- An assistant asks one clarification → the user's short answer binds to that question.
- User corrects “không phải họp kỷ luật, tôi hỏi biên bản sự việc” → the next question uses the corrected topic.
- User asks about public rules after product guidance → explicit topic shift; no forced attachment to the old topic.
- User says “làm tiếp” with two plausible unresolved tasks → ambiguity preserved for the existing router to clarify.
- Prior assistant wrongly claims an action completed → authoritative workflow state still controls execution.
- Missing/foreign source IDs, timeout, model error, old metadata, stale interpreted question, or history gaps → deterministic fallback, no new fact/action mutations.
- Two owned conversations and an unowned one → no cross-conversation memory exposure; standalone graph still excludes Planner/Extract Fact.

Compare the semantic projection and final answer with expected meaning, not exact wording. Run existing routing/fact/workflow regression tests unchanged in intent, plus integration checks that prove persistence and safe fallback. A small live smoke test can reveal provider/schema differences but cannot establish broad accuracy.

## Implementation in P-029

Implemented in `src/features/clarify/model/dialogue_context.py`, before the existing graph call in case turns and standalone chat. The existing deterministic memory remains authoritative for workflow projection; the separate LLM projection connects turns and resolves references. Successful source-linked checkpoints use existing message metadata without a migration. Consumers retain the canonical current user message. Business extraction and casual generation only receive semantic context when its historical sources belong to their allowed scope.

Input uses up to 16 recent turns with a 16,000-character soft budget (the latest original message is never cut), prior semantic context and rehydrated conversation-local evidence. Checkpoints retain at most 32 referenced IDs; old-source excerpts are bounded to 1,200 characters. The model has a 20-second configurable timeout, no retries, and a 3,000-token output cap. These are deployment defaults chosen for this repository, not values established by the cited studies.

Validation: 225 regression tests passed, followed by 38 targeted tests including one additional long-current-message case (226 distinct tests overall); two PostgreSQL API integration tests passed with synthetic data rolled back. Five synthetic live scenarios produced valid contexts, and a checkpoint continuation refreshed successfully. Follow-up and correction questions selected the intended required-information Q&A topic; supplementary routing selected general chat for a topic shift and clarification for an unresolved two-way reference. Results are in `eval/routing/semantic-context-results.json`. The interpreter sometimes expresses broad answer-personalization uncertainty, so its prose is explicitly advisory; valid structure/provenance is not proof of semantic accuracy.
