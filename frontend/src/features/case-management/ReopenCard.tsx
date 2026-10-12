import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useMe } from "@/app/providers";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { clearIdempotency, idempotencyKey } from "@/lib/idempotency";
import { api, errorMessage } from "@/services/api";

export function ReopenCard() {
  const { caseId, caseView } = useWorkspace();
  const me = useMe();
  const role = me.data?.role ?? "";
  const queryClient = useQueryClient();
  const [target, setTarget] = useState<"NEED_INFO" | "ANALYZED">("NEED_INFO");
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const note = useQuery({
    queryKey: ["latest-review", caseId],
    queryFn: () => api.latestReview(caseId),
    enabled: caseView.status === "REJECTED",
  });
  const reopen = useMutation({
    mutationFn: () => api.reopen(caseId, target, idempotencyKey(`reopen:${caseId}`)),
    onSuccess: (view) => {
      clearIdempotency(`reopen:${caseId}`);
      setOpen(false);
      setError(null);
      queryClient.setQueryData(["case", caseId], (current: { status?: string } | undefined) =>
        current ? { ...current, status: view.status } : current,
      );
      void queryClient.invalidateQueries({ queryKey: ["case", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["answer", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["facts", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["timeline", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (err) => setError(errorMessage(err)),
  });

  if (caseView.status !== "REJECTED" || (role !== "HR" && role !== "MANAGER")) return null;

  return (
    <section className="rounded-xl border border-son-line bg-son-tint px-4 py-3 text-sm text-son-dark">
      <p className="font-medium">Pháp chế đã trả hồ sơ</p>
      <p className="mt-1">Pháp chế yêu cầu xử lý lại. HR mở lại để bổ sung, rồi gửi phiếu hoặc chuyển quản lý.</p>
      {note.data?.comment ? <p className="mt-2 whitespace-pre-wrap">Ghi chú pháp chế: {note.data.comment}</p> : null}
      {error ? <p className="mt-2 text-son-dark">{error}</p> : null}
      {open ? (
        <div className="mt-3 space-y-2">
          <label className="block text-xs font-medium" htmlFor="reopen-target">
            Trở lại
          </label>
          <select
            id="reopen-target"
            className="h-9 rounded-md border border-son-line bg-white px-2 text-sm text-ink"
            value={target}
            onChange={(event) => setTarget(event.target.value as "NEED_INFO" | "ANALYZED")}
          >
            <option value="NEED_INFO">Cần bổ sung tình tiết</option>
            <option value="ANALYZED">Giữ đánh giá đã lưu</option>
          </select>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Hủy
            </Button>
            <Button disabled={reopen.isPending} onClick={() => reopen.mutate()}>
              {reopen.isPending ? "Đang mở lại…" : "Mở lại hồ sơ"}
            </Button>
          </div>
        </div>
      ) : (
        <Button className="mt-3" variant="secondary" onClick={() => setOpen(true)}>
          Mở lại hồ sơ
        </Button>
      )}
    </section>
  );
}
