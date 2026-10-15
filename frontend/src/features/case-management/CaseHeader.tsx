import { AlertTriangle, MessageSquareText } from "lucide-react";
import { Link, NavLink } from "react-router-dom";

import { StatusBadge } from "@/components/common/StatusBadge";
import { CASE_SECTIONS } from "@/features/case-management/case-navigation";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { riskLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

export function CaseHeader() {
  const { caseId, caseView, facts, answer } = useWorkspace();
  const base = `/cases/${caseId}`;
  const highRisk = answer?.risk_level === "HIGH" || answer?.risk_level === "CRITICAL";

  return (
    <header className="flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-rule bg-paper px-4 py-2.5 lg:px-6" aria-label="Thông tin và điều hướng hồ sơ">
      <div className="flex min-w-0 items-center gap-3">
        <Link to={base} className="flex min-w-0 items-center gap-2.5 rounded-md" aria-label="Về hội thoại hồ sơ" title="Về hội thoại hồ sơ">
          <MessageSquareText className="h-5 w-5 shrink-0 text-son" aria-hidden="true" />
          <h1 className="truncate text-base font-semibold uppercase text-ink">{caseView.case_code}</h1>
        </Link>
        <span className="hidden sm:inline-flex"><StatusBadge status={caseView.status} /></span>
        {highRisk ? (
          <Link to={`${base}/overview`} aria-label={`Xem cảnh báo rủi ro ${riskLabel(answer?.risk_level)}`} title={`Rủi ro ${riskLabel(answer?.risk_level)} — xem chi tiết`} className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-son-tint text-son-dark">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          </Link>
        ) : null}
      </div>
      <nav className="flex max-w-full shrink-0 items-center gap-0.5 overflow-x-auto" aria-label="Công cụ hồ sơ">
        {CASE_SECTIONS.map((item) => (
          <NavLink key={item.path} id={`case-tool-${item.path}`} to={`${base}/${item.path}`} title={item.label} aria-label={item.label} aria-haspopup="dialog" className={({ isActive }) => cn("relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors hover:bg-paper-2", isActive ? "bg-son-tint text-son-dark" : "text-ink-3")}>
            <item.icon className="h-[18px] w-[18px]" aria-hidden="true" />
            {item.path === "facts" && Boolean(facts?.missing_fact_keys.length) ? <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-son" aria-hidden="true" /> : null}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
