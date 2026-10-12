import { AlertTriangle, Check, Circle, Pencil } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { FactView } from "@/types/api";

export function FactItem({ fact, onEdit }: { fact: FactView; onEdit?: (fact: FactView) => void }) {
  const unknown = !fact.fact_value;
  const confirmed = Boolean(fact.fact_value) && fact.confirmed;
  const label = unknown ? "Chưa có" : confirmed ? "Đã xác nhận" : "AI nhận diện, chưa xác nhận";
  const Icon = unknown ? AlertTriangle : confirmed ? Check : Circle;
  const tone = unknown ? "text-son-dark" : confirmed ? "text-ink-2" : "text-ink-3";
  return (
    <li className="flex gap-2 border-b border-rule py-2 last:border-b-0">
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${tone}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium text-ink">{fact.label}</p>
          {onEdit && fact.fact_value ? (
            <Button variant="ghost" size="sm" onClick={() => onEdit(fact)}>
              <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
              Sửa
            </Button>
          ) : null}
        </div>
        <p className={`text-sm ${unknown ? "text-son-dark" : "text-ink"}`}>{fact.fact_value || "Chưa có"}</p>
        <p className={`text-xs ${tone}`}>{label}</p>
        {typeof fact.confidence === "number" ? (
          <p className="text-xs text-ink-3">Độ tin cậy AI: {fact.confidence.toFixed(2)}</p>
        ) : null}
      </div>
    </li>
  );
}
