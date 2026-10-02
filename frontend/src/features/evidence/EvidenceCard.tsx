import { Button } from "@/components/ui/button";
import { EVIDENCE_KIND_LABEL } from "@/lib/labels";
import { clip, placeLabel } from "@/lib/utils";
import type { EvidenceItem } from "@/types/api";

export function EvidenceCard({ item, onOpen }: { item: EvidenceItem; onOpen: (item: EvidenceItem) => void }) {
  const place = placeLabel(item.article, item.clause, item.point);
  return (
    <article
      className={`rounded-lg border bg-white ${item.kind === "ADMINISTRATIVE_PENALTY" ? "border-amber-300 bg-amber-50" : "border-[#d5e8ed]"}`}
    >
      <header className="flex items-start justify-between gap-3 border-b border-neutral-100 px-3 py-2">
        <div>
          <p className="text-xs font-semibold tracking-wide text-neutral-500">{EVIDENCE_KIND_LABEL[item.kind]}</p>
          <h3 className="text-sm font-medium text-neutral-900">
            {[item.policyCode, item.policyName].filter(Boolean).join(" · ") || "Văn bản"}
          </h3>
          {place ? <p className="text-xs text-neutral-500">{place}</p> : null}
        </div>
      </header>
      {item.kind === "ADMINISTRATIVE_PENALTY" ? (
        <p className="px-3 pt-3 text-xs text-amber-950">Rủi ro thanh tra, không phải mức kỷ luật của người lao động.</p>
      ) : null}
      {item.kind === "PRECEDENT" ? (
        <p className="px-3 pt-3 text-xs text-[#4d7380]">Tiền lệ để tham khảo. Không tự quyết mức của vụ này.</p>
      ) : null}
      <p className="whitespace-pre-wrap px-3 py-3 text-sm leading-6 text-neutral-800">{clip(item.content, 420)}</p>
      {item.retrievedBecause ? (
        <p className="px-3 pb-3 text-xs text-neutral-500">Đối chiếu theo: {clip(item.retrievedBecause, 180)}</p>
      ) : null}
      <footer className="flex items-center justify-between gap-3 border-t border-neutral-100 px-3 py-2 text-xs text-neutral-500">
        <span>Mã đoạn: {item.chunkId || "—"}</span>
        <Button variant="ghost" size="sm" onClick={() => onOpen(item)}>
          Xem nguồn
        </Button>
      </footer>
    </article>
  );
}
