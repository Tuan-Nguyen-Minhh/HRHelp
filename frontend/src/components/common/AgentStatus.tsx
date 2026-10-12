import { AlertTriangle, CheckCircle2, LoaderCircle } from "lucide-react";

import { AGENT_LABEL, AGENT_STATUS_LABEL } from "@/lib/labels";
import type { AgentEvent } from "@/types/api";

export function AgentStatus({ agent }: { agent: AgentEvent | null }) {
  if (!agent) {
    return (
      <span className="inline-flex items-center gap-2 text-xs font-medium text-ink-3 rounded border border-rule bg-paper-2 px-3 py-1.5">
        <span className="h-2 w-2 rounded-full bg-rule-2" aria-hidden="true" />
        Chưa có lượt xử lý trong phiên này
      </span>
    );
  }
  const Icon = agent.status === "running" ? LoaderCircle : agent.status === "failed" ? AlertTriangle : CheckCircle2;
  const color =
    agent.status === "running" ? "text-son-dark" : agent.status === "failed" ? "text-son-dark" : "text-ink-2";
  const bgColor =
    agent.status === "running" ? "border-son-line bg-son-tint" : "border-rule bg-paper-2";

  return (
    <span className={`inline-flex items-center gap-2 text-xs font-medium rounded border px-3 py-1.5 ${color} ${bgColor}`}>
      {agent.status === "running" && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-son opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-son"></span>
        </span>
      )}
      <Icon className={`h-3.5 w-3.5 ${agent.status === "running" ? "animate-spin" : ""}`} aria-hidden="true" />
      <span>
        {AGENT_LABEL[agent.agent]} {AGENT_STATUS_LABEL[agent.status]}
      </span>
    </span>
  );
}
