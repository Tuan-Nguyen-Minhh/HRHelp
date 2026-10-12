import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useMe } from "@/app/providers";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/services/api";

function caseHref(role: string, caseId: string): string {
  if (role === "LEGAL") return `/legal-review/${caseId}`;
  if (role === "MANAGER") return `/manager/${caseId}`;
  if (role === "SIGNER") return `/decisions/${caseId}`;
  return `/cases/${caseId}`;
}

export function NotificationsPage() {
  const me = useMe();
  const role = me.data?.role ?? "";
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["notifications"], queryFn: () => api.notifications() });
  const read = useMutation({
    mutationFn: (id: string) => api.readNotification(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const items = query.data?.notifications ?? [];
  const unread = items.filter((item) => !item.read_at).length;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <p className="text-xs font-semibold tracking-[0.16em] text-son-dark">THÔNG BÁO</p>
        <h1 className="text-2xl font-semibold text-ink">Việc mới · {unread} chưa đọc</h1>
      </div>
      {query.isLoading ? (<div className="space-y-3" role="status" aria-label="Đang tải thông báo">{Array.from({ length: 3 }).map((_, i) => (<div key={i} className="skeleton h-20" aria-hidden="true" />))}</div>) : null}
      {query.isError ? <p className="text-sm text-son-dark">{errorMessage(query.error)}</p> : null}
      {!query.isLoading && items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-rule-2 bg-white px-4 py-8 text-sm text-ink-3">Chưa có thông báo.</p>
      ) : null}
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.id} className="rounded-xl border border-rule bg-white px-4 py-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-medium text-ink">{item.title}</p>
                <p className="mt-1 text-sm text-ink-2">{item.body}</p>
                <p className="mt-1 text-xs text-ink-3">{new Date(item.created_at).toLocaleString("vi-VN")}</p>
              </div>
              {item.read_at ? <span className="text-xs text-ink-3">Đã đọc</span> : (
                <Button size="sm" variant="secondary" onClick={() => read.mutate(item.id)}>
                  Đánh dấu đã đọc
                </Button>
              )}
            </div>
            {item.case_id ? (
              <Link className="mt-2 inline-block text-sm text-son-dark underline" to={caseHref(role, item.case_id)}>
                Mở hồ sơ
              </Link>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
