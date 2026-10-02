import type { AgentEvent, AgentName, AgentRunStatus } from "@/types/api";

const AGENTS = new Set<AgentName>(["clarification", "retrieval", "evidence_synthesis", "decision", "legal_review"]);
const STATUSES = new Set<AgentRunStatus>(["running", "completed", "failed"]);

function asEvent(value: unknown): AgentEvent | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  if (record.type !== "agent_status") return null;
  if (typeof record.agent !== "string" || !AGENTS.has(record.agent as AgentName)) return null;
  if (typeof record.status !== "string" || !STATUSES.has(record.status as AgentRunStatus)) return null;
  return { type: "agent_status", agent: record.agent as AgentName, status: record.status as AgentRunStatus };
}

/**
 * Subscribe when the deployment sets VITE_AGENT_EVENTS_URL.
 * The current API does not emit agent events, so the default is a no-op.
 */
export function subscribeAgentEvents(caseId: string, onEvent: (event: AgentEvent) => void): () => void {
  const base = import.meta.env.VITE_AGENT_EVENTS_URL;
  if (!base || typeof EventSource === "undefined") return () => {};
  const url = new URL(base, window.location.origin);
  url.searchParams.set("case_id", caseId);
  const source = new EventSource(url);
  const handle = (raw: MessageEvent<string>) => {
    try {
      const event = asEvent(JSON.parse(raw.data));
      if (event) onEvent(event);
    } catch {
      // Ignore a frame that is not the status payload.
    }
  };
  source.addEventListener("agent_status", handle);
  source.onmessage = handle;
  return () => source.close();
}
