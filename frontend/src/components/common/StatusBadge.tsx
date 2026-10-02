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
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      <span>{statusLabel(status)}</span>
      <span className="font-normal text-current/80">{status}</span>
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
