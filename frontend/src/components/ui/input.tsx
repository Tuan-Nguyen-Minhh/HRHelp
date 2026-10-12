import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-md border border-rule bg-paper px-3.5 text-sm text-ink placeholder:text-ink-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-son/30 focus-visible:border-son transition-colors duration-200 disabled:cursor-not-allowed disabled:bg-paper-2",
        className,
      )}
      {...props}
    />
  );
});
