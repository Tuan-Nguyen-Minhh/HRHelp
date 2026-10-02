import { Sheet } from "@/components/ui/sheet";
import { EVIDENCE_KIND_LABEL } from "@/lib/labels";
import { placeLabel } from "@/lib/utils";
import type { EvidenceItem } from "@/types/api";

export function EvidenceDrawer({ item, onClose }: { item: EvidenceItem | null; onClose: () => void }) {
  return (
    <Sheet open={Boolean(item)} onOpenChange={(open) => !open && onClose()} title="Căn cứ">
      {item ? (
        <div className="space-y-4 text-sm">
          <div>
            <p className="text-xs text-neutral-500">Văn bản</p>
            <p className="font-medium">{item.policyName || item.policyCode || "—"}</p>
            <p className="text-neutral-600">{EVIDENCE_KIND_LABEL[item.kind]}</p>
          </div>
          <div>
            <p className="text-xs text-neutral-500">Vị trí</p>
            <p>{placeLabel(item.article, item.clause, item.point) || "—"}</p>
          </div>
          <div>
            <p className="text-xs text-neutral-500">Đoạn đã lấy</p>
            <p className="mt-1 whitespace-pre-wrap leading-6">{item.content}</p>
          </div>
          <div>
            <p className="text-xs text-neutral-500">Mã đoạn</p>
            <p className="break-all">{item.chunkId || "—"}</p>
          </div>
          {item.caseCode ? (
            <div>
              <p className="text-xs text-neutral-500">Hồ sơ</p>
              <p>{item.caseCode}</p>
            </div>
          ) : null}
          {item.retrievedBecause ? (
            <div>
              <p className="text-xs text-neutral-500">Truy vấn đối chiếu</p>
              <p className="whitespace-pre-wrap text-neutral-700">{item.retrievedBecause}</p>
            </div>
          ) : null}
        </div>
      ) : null}
    </Sheet>
  );
}
