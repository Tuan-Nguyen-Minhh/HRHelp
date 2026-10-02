import { AlertTriangle, CheckCircle2, LoaderCircle } from "lucide-react";

import { AGENT_LABEL, AGENT_STATUS_LABEL } from "@/lib/labels";
import type { AgentEvent } from "@/types/api";

export function AgentStatus({ agent }: { agent: AgentEvent | null }) {
  if (!agent) {
    return (
      <span className="inline-flex items-center gap-2 text-xs text-neutral-500">
        <span className="h-2 w-2 rounded-full bg-neutral-300" aria-hidden="true" />
        Chưa có lượt xử lý trong phiên này
      </span>
    );
  }
  const Icon = agent.status === "running" ? LoaderCircle : agent.status === "failed" ? AlertTriangle : CheckCircle2;
  const color =
    agent.status === "running" ? "text-sky-800" : agent.status === "failed" ? "text-red-800" : "text-emerald-800";
  return (
    <span className={`inline-flex items-center gap-2 text-xs font-medium ${color}`}>
      <Icon className={`h-3.5 w-3.5 ${agent.status === "running" ? "animate-spin" : ""}`} aria-hidden="true" />
      {AGENT_LABEL[agent.agent]} {AGENT_STATUS_LABEL[agent.status]}
    </span>
  );
}
