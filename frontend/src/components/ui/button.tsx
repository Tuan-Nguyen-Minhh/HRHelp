import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009EC1] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-[#009EC1] text-white hover:bg-[#0087A6]",
        secondary: "border border-[#d5e8ed] bg-white text-[#073642] hover:bg-[#f4fafb]",
        outline: "border border-neutral-300 bg-white hover:bg-neutral-50",
        ghost: "hover:bg-neutral-100",
        destructive: "bg-red-700 text-white hover:bg-red-800",
      },
      size: {
        default: "h-9 px-3",
        sm: "h-8 px-2.5 text-xs",
        lg: "h-10 px-4",
        icon: "h-9 w-9",
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
