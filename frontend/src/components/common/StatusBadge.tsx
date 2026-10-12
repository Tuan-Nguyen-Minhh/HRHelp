import { AlertTriangle, CheckCircle2, CircleDashed, Info, MinusCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { statusLabel, statusTone, type StatusTone } from "@/lib/labels";

const icons = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: AlertTriangle,
  neutral: MinusCircle,
};

export function StatusBadge({ status }: { status: string }) {
  const tone = statusTone(status);
  const Icon = icons[tone];
  return (
    <Badge tone={tone}>
      {status === "running" && (
        <span className="relative flex h-2 w-2 -mr-0.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-current"></span>
        </span>
      )}
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      <span>{statusLabel(status)}</span>
    </Badge>
  );
}

export function ToneBadge({ tone, label }: { tone: StatusTone; label: string }) {
  const Icon = tone === "neutral" ? CircleDashed : icons[tone];
  return (
    <Badge tone={tone}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </Badge>
  );
}
