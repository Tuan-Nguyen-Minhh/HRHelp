import type { HTMLAttributes } from "react";

import type { StatusTone } from "@/lib/labels";
import { cn } from "@/lib/utils";

/* Monochrome value-steps + vermilion for "needs action".
   See design-system/hr-help/MASTER.md §2. */
const tones: Record<StatusTone, string> = {
  info: "border-rule bg-paper-3 text-ink-2",
  success: "border-leather bg-leather text-paper",
  warning: "border-son-line bg-son-tint text-son-dark",
  danger: "border-son bg-son text-white",
  neutral: "border-rule bg-transparent text-ink-3",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: StatusTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-2.5 py-0.5 text-xs font-semibold tracking-wide",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
