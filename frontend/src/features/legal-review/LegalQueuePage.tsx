import { useQuery } from "@tanstack/react-query";

import { Card } from "@/components/ui/card";
import { LegalQueueTable } from "@/features/legal-review/LegalQueueTable";
import { api, errorMessage } from "@/services/api";

export function LegalQueuePage() {
  const query = useQuery({ queryKey: ["legal-queue"], queryFn: () => api.legalQueue() });
  const rows = query.data?.reviews ?? [];
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-semibold tracking-[0.16em] text-son-dark">PHÁP CHẾ</p>
        <h1 className="text-2xl font-semibold text-ink">Phiếu đang chờ duyệt</h1>
        <p className="mt-1 text-sm text-ink-3">Mọi phiếu HR vừa gửi. Duyệt để chuyển quản lý, hoặc yêu cầu HR xử lý lại.</p>
      </div>
      <Card className="overflow-hidden">
        <LegalQueueTable rows={rows} loading={query.isLoading} error={query.isError ? errorMessage(query.error) : null} showUpdated />
      </Card>
    </div>
  );
}
