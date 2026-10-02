import { NavLink } from "react-router-dom";

import { StatusBadge } from "@/components/common/StatusBadge";
import { familyLabel } from "@/lib/labels";
import { cn, formatDate } from "@/lib/utils";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";

const LINKS = [
  { to: "", label: "Tổng quan", end: true },
  { to: "conversation", label: "Hội thoại", end: false },
  { to: "facts", label: "Tình tiết", end: false },
  { to: "evidence", label: "Căn cứ", end: false },
  { to: "assessment", label: "Đánh giá", end: false },
  { to: "documents", label: "Văn bản", end: false },
  { to: "timeline", label: "Dòng thời gian", end: false },
  { to: "decision", label: "Phiếu", end: false },
  { to: "legal-review", label: "Gói duyệt", end: false },
];

export function CaseHeader() {
  const { caseId, caseView, facts, answer } = useWorkspace();
  const violation = firstLine(caseView.description);
  return (
    <header className="rounded-xl border border-[#d5e8ed] bg-white px-4 py-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold tracking-[0.16em] text-[#009EC1]">HỒ SƠ</p>
          <h1 className="text-2xl font-semibold text-[#073642]">#{caseView.case_code}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={caseView.status} />
          {answer?.risk_level ? (
            <span className="rounded-md border border-[#d5e8ed] bg-[#f4fafb] px-2 py-1 text-xs text-[#073642]">
              Rủi ro {answer.risk_level}
            </span>
          ) : null}
        </div>
      </div>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
        <div>
          <dt className="text-xs text-[#4d7380]">Nhân viên</dt>
          <dd className="font-medium text-[#073642]">{caseView.employee_name || "—"}</dd>
          <dd className="text-xs text-[#4d7380]">{caseView.employee_code || "Chưa có mã"}</dd>
        </div>
        <div>
          <dt className="text-xs text-[#4d7380]">Sự việc</dt>
          <dd className="line-clamp-2 font-medium text-[#073642]">{violation || "Chưa có mô tả"}</dd>
        </div>
        <div>
          <dt className="text-xs text-[#4d7380]">Ngày xảy ra</dt>
          <dd className="font-medium text-[#073642]">{formatDate(caseView.incident_date)}</dd>
        </div>
        <div>
          <dt className="text-xs text-[#4d7380]">Nhóm</dt>
          <dd className="font-medium text-[#073642]">{familyLabel(caseView.family || facts?.family)}</dd>
        </div>
      </dl>
      <nav className="mt-4 flex gap-1 overflow-x-auto" aria-label="Phần hồ sơ">
        {LINKS.map((item) => (
          <NavLink
            key={item.label}
            to={item.to ? `/cases/${caseId}/${item.to}` : `/cases/${caseId}`}
            end={item.end}
            className={({ isActive }) =>
              cn(
                "shrink-0 rounded-full px-3 py-1.5 text-xs font-medium",
                isActive ? "bg-[#009EC1] text-white" : "bg-[#e7f6f9] text-[#073642] hover:bg-[#d3eef4]",
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}

function firstLine(value: string | null): string {
  if (!value) return "";
  const line = value
    .split("\n")
    .map((item) => item.trim())
    .find(Boolean);
  return line ?? "";
}
