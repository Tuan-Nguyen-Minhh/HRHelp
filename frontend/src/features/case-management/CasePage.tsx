import { AgentStatus } from "@/components/common/AgentStatus";
import { CaseOverview } from "@/features/case-management/CaseOverview";
import { CaseProgress } from "@/features/case-management/CaseProgress";
import { ReopenCard } from "@/features/case-management/ReopenCard";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";

export function CasePage() {
  const { agent, answer } = useWorkspace();
  const highRisk = answer?.risk_level === "HIGH" || answer?.risk_level === "CRITICAL";
  return (
    <div className="space-y-4">
      {highRisk ? <p className="rounded-xl border border-son-line bg-son-tint px-4 py-3 text-sm leading-6 text-son-dark">Vụ việc có mức rủi ro cao. Hãy kiểm tra căn cứ và chứng cứ trước khi xử lý. Mức rủi ro không tự quyết hình thức kỷ luật.</p> : null}
      <CaseOverview />
      <CaseProgress />
      <AgentStatus agent={agent} />
      <ReopenCard />
    </div>
  );
}
