import { useMemo, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { EvidenceCard } from "@/features/evidence/EvidenceCard";
import { EvidenceDrawer } from "@/features/evidence/EvidenceDrawer";
import { evidenceItems } from "@/lib/evidence";
import { EVIDENCE_KIND_LABEL } from "@/lib/labels";
import type { EvidenceItem, EvidenceKind } from "@/types/api";

const TABS: Array<EvidenceKind | "ALL"> = ["ALL", "LAW", "DECREE", "INTERNAL_RULE", "PRECEDENT", "ADMINISTRATIVE_PENALTY"];

export function EvidencePanel() {
  const { answer, handoff, caseView } = useWorkspace();
  const [selected, setSelected] = useState<EvidenceItem | null>(null);
  const items = useMemo(
    () => evidenceItems(answer, handoff, caseView.case_code),
    [answer, handoff, caseView.case_code],
  );

  return (
    <Card id="can-cu" className="scroll-mt-4">
      <CardHeader>
        <div>
          <CardTitle>Căn cứ đã lấy</CardTitle>
          <p className="mt-1 text-xs text-[#4d7380]">
            Phân loại theo lớp backend đã trả. Xử phạt hành chính là rủi ro thanh tra, không phải mức kỷ luật của người lao động.
          </p>
        </div>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-neutral-600">Chưa có đoạn căn cứ.</p>
        ) : (
          <Tabs defaultValue="ALL">
            <TabsList>
              {TABS.map((tab) => {
                const count = tab === "ALL" ? items.length : items.filter((item) => item.kind === tab).length;
                const label = tab === "ALL" ? "Tất cả" : EVIDENCE_KIND_LABEL[tab];
                return (
                  <TabsTrigger key={tab} value={tab}>
                    {label}
                    <span className="text-neutral-400">{count}</span>
                  </TabsTrigger>
                );
              })}
            </TabsList>
            {TABS.map((tab) => {
              const rows = tab === "ALL" ? items : items.filter((item) => item.kind === tab);
              return (
                <TabsContent key={tab} value={tab}>
                  {rows.length === 0 ? (
                    <p className="text-sm text-neutral-600">Không có đoạn trong nhóm này.</p>
                  ) : (
                    <div className="grid gap-3 xl:grid-cols-2">
                      {rows.map((item) => (
                        <EvidenceCard key={item.id} item={item} onOpen={setSelected} />
                      ))}
                    </div>
                  )}
                </TabsContent>
              );
            })}
          </Tabs>
        )}
      </CardContent>
      <EvidenceDrawer item={selected} onClose={() => setSelected(null)} />
    </Card>
  );
}
