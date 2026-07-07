"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-[var(--ar-radius-md)] text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)] disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98] hover:scale-[1.02]",
  {
    variants: {
      variant: {
        default: "bg-[var(--ar-cloud)] text-[var(--ar-black)] hover:bg-white",
        ghost: "text-[var(--ar-cloud)] hover:bg-white/8",
        accent:
          "bg-gradient-to-r from-[var(--ar-indigo)] via-[var(--ar-sky)] to-[var(--ar-cyan)] text-white hover:opacity-90 shadow-lg shadow-[var(--ar-sky)]/20",
        outline: "border border-white/20 text-[var(--ar-cloud)] hover:border-[var(--ar-sky)]/50 hover:bg-white/5",
      },
      size: {
        default: "h-10 px-4 py-2",
        lg: "h-12 px-6 text-base",
        sm: "h-8 px-3 text-xs",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
