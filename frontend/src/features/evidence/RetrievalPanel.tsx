import { Check, Circle, LoaderCircle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { countByKind, evidenceItems } from "@/lib/evidence";
import { EVIDENCE_KIND_LABEL, RETRIEVAL_LABEL } from "@/lib/labels";

export function RetrievalPanel() {
  const { facts, answer, handoff, agent } = useWorkspace();
  const running = agent?.status === "running";
  const items = evidenceItems(answer, handoff, null);
  const counts = countByKind(items);
  const retrieval = handoff?.retrieval;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{answer || handoff ? "Kết quả đối chiếu đã lưu" : "Đối chiếu văn bản"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <ul className="space-y-2 text-sm">
          <Row
            done={Boolean(facts?.facts_locked)}
            active={running && !facts?.facts_locked}
            label="Tình tiết bắt buộc"
            detail={facts?.facts_locked ? "Đã đủ" : facts ? "Còn thiếu" : "Đang tải"}
          />
          <Row
            done={Boolean(handoff || answer)}
            active={running && Boolean(facts?.facts_locked)}
            label="Đối chiếu văn bản"
            detail={retrieval ? (RETRIEVAL_LABEL[retrieval] ?? retrieval) : answer ? "Đã có báo cáo" : "Chưa chạy"}
          />
          <Row done={Boolean(answer)} active={false} label="Đánh giá căn cứ" detail={answer ? "Đã lưu báo cáo" : "Chưa có báo cáo"} />
        </ul>
        {items.length > 0 ? (
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            {(["LAW", "DECREE", "INTERNAL_RULE", "PRECEDENT", "ADMINISTRATIVE_PENALTY"] as const).map((kind) => (
              <li key={kind} className="rounded-md border border-rule px-3 py-2">
                <p className="text-xs text-ink-3">{EVIDENCE_KIND_LABEL[kind]}</p>
                <p className="text-lg font-semibold">{counts[kind]}</p>
                <p className="text-xs text-ink-3">đoạn</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-2">
            {facts?.facts_locked
              ? "Tình tiết đã đủ. Đoạn văn bản xuất hiện sau lượt đối chiếu."
              : "Đối chiếu bắt đầu khi backend báo tình tiết bắt buộc đã đủ."}
          </p>
        )}
        {handoff?.missing_internal_rule ? (
          <p className="text-sm text-son-dark">Backend đánh dấu lượt này chưa giữ được đoạn nội quy.</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Row({ done, active, label, detail }: { done: boolean; active: boolean; label: string; detail: string }) {
  const Icon = active ? LoaderCircle : done ? Check : Circle;
  const tone = active ? "text-son-dark" : done ? "text-ink-2" : "text-ink-4";
  return (
    <li className="flex items-start gap-2">
      <Icon className={`mt-0.5 h-4 w-4 ${tone} ${active ? "animate-spin" : ""}`} aria-hidden="true" />
      <span>
        <span className="font-medium text-ink">{label}</span>
        <span className="mt-0.5 block text-xs text-ink-3">{detail}</span>
      </span>
    </li>
  );
}
