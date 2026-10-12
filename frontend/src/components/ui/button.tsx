import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-semibold transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-son/40 disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
  {
    variants: {
      variant: {
        default: "bg-son text-white hover:bg-son-dark",
        secondary: "border border-rule-2 bg-paper text-ink-2 hover:bg-paper-2 hover:text-ink",
        outline: "border border-rule-2 bg-paper text-ink-2 hover:border-ink-3 hover:text-ink",
        ghost: "text-ink-2 hover:bg-paper-2 hover:text-ink",
        destructive: "bg-son-dark text-white hover:bg-son",
      },
      size: {
        default: "h-10 px-4",
        sm: "h-9 px-3 text-xs",
        lg: "h-11 px-5",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, asChild = false, type = "button", ...props },
  ref,
) {
  const classNames = cn(buttonVariants({ variant, size }), className);
  if (asChild) return <Slot ref={ref} className={classNames} {...props} />;
  return <button ref={ref} type={type} className={classNames} {...props} />;
});
