import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EvidenceDrawer } from "@/features/evidence/EvidenceDrawer";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { evidenceItems } from "@/lib/evidence";
import { placeLabel } from "@/lib/utils";
import type { EvidenceItem } from "@/types/api";

export function PrecedentSection() {
  const items = useLayer("PRECEDENT");
  return (
    <Card>
      <CardHeader>
        <CardTitle>Tiền lệ tham khảo</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-ink-2">
          {items.length} đoạn tiền lệ. Đây là tham chiếu ngữ cảnh. Tiền lệ không nằm trong danh sách mức kỷ luật của công ty.
        </p>
        <ReferenceList items={items} empty="Lượt này không có tiền lệ." />
      </CardContent>
    </Card>
  );
}

export function AdministrativeSection() {
  const items = useLayer("ADMINISTRATIVE_PENALTY");
  return (
    <Card className="border-son-line bg-son-tint/40">
      <CardHeader>
        <CardTitle>Xử phạt hành chính</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="font-medium text-son-dark">Nhóm này không phải chế tài kỷ luật đối với người lao động.</p>
        <p className="text-ink-2">Backend tách các đoạn xử phạt hành chính khỏi mức kỷ luật của công ty.</p>
        <ReferenceList items={items} empty="Lượt này không có đoạn xử phạt hành chính." />
      </CardContent>
    </Card>
  );
}

function useLayer(kind: EvidenceItem["kind"]): EvidenceItem[] {
  const { answer, handoff, caseView } = useWorkspace();
  return evidenceItems(answer, handoff, caseView.case_code).filter((item) => item.kind === kind);
}

function ReferenceList({ items, empty }: { items: EvidenceItem[]; empty: string }) {
  const [selected, setSelected] = useState<EvidenceItem | null>(null);
  if (!items.length) return <p className="text-ink-2">{empty}</p>;
  return (
    <>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.id} className="rounded-md border border-rule bg-white px-3 py-2">
            <p className="font-medium">{item.policyName || item.policyCode || "Văn bản"}</p>
            <p className="text-xs text-ink-3">
              {placeLabel(item.article, item.clause, item.point) || "Không có vị trí điều khoản"}
            </p>
            <Button className="mt-1 px-0" variant="ghost" size="sm" onClick={() => setSelected(item)}>
              Xem nguồn
            </Button>
          </li>
        ))}
      </ul>
      <EvidenceDrawer item={selected} onClose={() => setSelected(null)} />
    </>
  );
}
