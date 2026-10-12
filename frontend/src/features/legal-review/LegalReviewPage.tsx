import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Sheet } from "@/components/ui/sheet";
import { DocumentSections, EvidenceDetail, sectionLinks } from "@/features/assessment/form/Sections";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { HOLD_LABEL } from "@/lib/labels";
import { api, errorMessage } from "@/services/api";
import type { EvidenceCard } from "@/types/assessment";

export function LegalReviewPage() {
  const { caseId, caseView, answer } = useWorkspace();
  const ticket = answer?.ticket ?? null;
  const queued = caseView.status === "PENDING_LEGAL" || ticket?.disposition === "SUBMIT";
  const assessment = useQuery({ queryKey: ["assessment", caseId], queryFn: () => api.getAssessment(caseId) });
  const [selected, setSelected] = useState<EvidenceCard | null>(null);

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <Card className={queued ? "border-son-line" : ""}>
        <CardHeader>
          <CardTitle>Pháp chế</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="font-medium">{queued ? "Hồ sơ đang ở hàng chờ pháp chế." : "Hồ sơ chưa được đẩy sang pháp chế."}</p>
          <p>{ticket?.reason || "Chưa có lý do từ phiếu."}</p>
          {ticket?.hold_code ? <p className="text-xs text-ink-3">{HOLD_LABEL[ticket.hold_code] ?? ticket.hold_code}</p> : null}
        </CardContent>
      </Card>

      {assessment.isLoading ? (<div className="space-y-2" role="status" aria-label="Đang tải biên bản">{Array.from({ length: 3 }).map((_, i) => (<div key={i} className="skeleton h-16" aria-hidden="true" />))}</div>) : null}
      {assessment.isError ? <p className="text-sm text-son-dark">{errorMessage(assessment.error)}</p> : null}
      {assessment.data ? (
        <div className="grid items-start gap-4 lg:grid-cols-[13rem_minmax(0,1fr)]">
          <nav className="flex gap-2 overflow-x-auto lg:sticky lg:top-4 lg:block lg:space-y-1" aria-label="Mục biên bản">
            {sectionLinks().map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="block shrink-0 rounded-md px-3 py-1.5 text-sm text-ink hover:bg-paper-2"
              >
                {item.label}
              </a>
            ))}
          </nav>
          <DocumentSections
            view={assessment.data}
            sections={assessment.data.sections}
            editing={null}
            saving={false}
            onBegin={() => undefined}
            onCancel={() => undefined}
            onSave={() => undefined}
            onCase={() => undefined}
            onEmployee={() => undefined}
            onIncident={() => undefined}
            onFacts={() => undefined}
            onRationale={() => undefined}
            onOpen={setSelected}
          />
        </div>
      ) : assessment.isLoading || assessment.isError ? null : (
        <Card>
          <CardHeader>
            <CardTitle>Biên bản</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-ink-3">Chưa có biên bản đã xác nhận.</CardContent>
        </Card>
      )}

      <Sheet open={selected !== null} onOpenChange={(open) => { if (!open) setSelected(null); }} title="Đoạn căn cứ">
        {selected ? <EvidenceDetail card={selected} /> : null}
      </Sheet>
    </div>
  );
}
