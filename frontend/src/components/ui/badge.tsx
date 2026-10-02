import type { HTMLAttributes } from "react";

import type { StatusTone } from "@/lib/labels";
import { cn } from "@/lib/utils";

const tones: Record<StatusTone, string> = {
  info: "border-[#9fd0db] bg-[#e7f6f9] text-[#073642]",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  warning: "border-amber-200 bg-amber-50 text-amber-950",
  danger: "border-red-200 bg-red-50 text-red-900",
  neutral: "border-neutral-200 bg-neutral-100 text-neutral-700",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: StatusTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
