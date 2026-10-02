import { AlertTriangle, CheckCircle2, LoaderCircle } from "lucide-react";

import { AGENT_LABEL, AGENT_STATUS_LABEL } from "@/lib/labels";
import type { AgentEvent } from "@/types/api";

export function AgentStatus({ agent }: { agent: AgentEvent | null }) {
  if (!agent) {
    return (
      <span className="inline-flex items-center gap-2 text-xs font-medium text-slate-400 rounded-full bg-slate-50 px-3 py-1.5">
        <span className="h-2 w-2 rounded-full bg-slate-300" aria-hidden="true" />
        Chưa có lượt xử lý trong phiên này
      </span>
    );
  }
  const Icon = agent.status === "running" ? LoaderCircle : agent.status === "failed" ? AlertTriangle : CheckCircle2;
  const color =
    agent.status === "running" ? "text-brand-700" : agent.status === "failed" ? "text-red-700" : "text-emerald-700";
  const bgColor = agent.status === "running" ? "bg-brand-50" : "bg-slate-50";

  return (
    <span className={`inline-flex items-center gap-2 text-xs font-medium rounded-full px-3 py-1.5 ${color} ${bgColor}`}>
      {agent.status === "running" && (
         <span className="relative flex h-2 w-2">
           <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75"></span>
           <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-500"></span>
         </span>
      )}
      <Icon className={`h-3.5 w-3.5 ${agent.status === "running" ? "animate-spin" : ""}`} aria-hidden="true" />
      <span>
        {AGENT_LABEL[agent.agent]} {AGENT_STATUS_LABEL[agent.status]}
      </span>
    </span>
  );
}
