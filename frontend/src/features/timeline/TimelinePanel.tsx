import { useQuery } from "@tanstack/react-query";

import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { isRawHandoffMessage } from "@/lib/report";
import { api, errorMessage } from "@/services/api";

export function TimelinePanel() {
  const { caseId } = useWorkspace();
  const query = useQuery({ queryKey: ["timeline", caseId], queryFn: () => api.timeline(caseId) });
  if (query.isLoading) return <p className="text-sm text-[#4d7380]">Đang ghép dòng thời gian…</p>;
  if (query.isError) return <p className="text-sm text-red-800">{errorMessage(query.error)}</p>;
  const events = (query.data?.events ?? []).filter((event) => !isRawHandoffMessage(event.label));
  if (events.length === 0) return <p className="text-sm text-[#4d7380]">Chưa có sự kiện đã lưu.</p>;
  return (
    <ol className="space-y-3">
      {events.map((event, index) => (
        <li key={`${event.at}-${event.kind}-${index}`} className="grid grid-cols-[9rem_minmax(0,1fr)] gap-3 rounded-xl border border-[#d5e8ed] bg-white px-3 py-2">
          <time className="text-xs text-[#4d7380]">{new Date(event.at).toLocaleString("vi-VN")}</time>
          <div>
            <p className="text-xs font-semibold tracking-wide text-[#009EC1]">{event.kind}</p>
            <p className="text-sm text-[#073642]">{event.label}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
